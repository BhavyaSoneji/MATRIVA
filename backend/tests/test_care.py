"""Care features: dating, plan, reminders, check-ins, readings, meals, red-flag screening, summary, privacy."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.services.care import dating, meals, readings, screening
from app.services.care.dating import DatingError

TODAY = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(dating, "today_utc", lambda: TODAY)


@pytest.fixture
def me(client: TestClient, auth_headers):
    """A signed-in user who has given consent, 22 weeks along."""
    assert client.put("/profile", headers=auth_headers, json={"consent": True, "consent_version": "v1.0", "diet_type": "vegetarian", "allergies": ["peanuts"]}).status_code == 200
    lmp = TODAY - timedelta(days=21 * 7 + 3)  # week 22, day 4
    assert client.put("/care/dating", headers=auth_headers, json={"lmp_date": lmp.isoformat(), "pre_pregnancy_weight_kg": 55}).status_code == 200
    return auth_headers


# ------------------------------------------------------------------------------------------------ dating
def test_week_from_lmp() -> None:
    lmp = date(2026, 1, 1)
    assert dating.week_from_lmp(lmp, date(2026, 1, 1)) == (1, 1)
    assert dating.week_from_lmp(lmp, date(2026, 1, 8)) == (2, 1)
    assert dating.week_from_lmp(lmp, date(2026, 1, 10)) == (2, 3)
    assert dating.week_from_lmp(lmp, date(2027, 1, 1))[0] == 42  # clamped


def test_dating_builds_edd_trimester_and_progress() -> None:
    d = dating.build(date(2026, 1, 1), "lmp", date(2026, 7, 9))
    assert d.edd == date(2026, 10, 8) and d.week == 28 and d.trimester == 3 and d.days_to_edd == 91
    assert 0.6 < d.progress < 0.7


@pytest.mark.parametrize("kwargs, message", [
    ({"lmp": TODAY + timedelta(days=3)}, "future"),
    ({"lmp": TODAY - timedelta(days=400)}, "42 weeks"),
    ({"lmp": TODAY, "edd": TODAY}, "exactly one"),
    ({}, "exactly one"),
    ({"week": 50}, "between 1 and 42"),
])
def test_dating_validation(client, auth_headers, kwargs, message) -> None:
    from app.core.db import SessionLocal
    from app.models import User

    client.put("/profile", headers=auth_headers, json={"consent": True, "consent_version": "v1.0"})
    with SessionLocal() as db:
        with pytest.raises(DatingError, match=message):
            dating.save(db, db.query(User).one(), today=TODAY, **kwargs)


def test_dating_needs_consent(client: TestClient, auth_headers) -> None:
    assert client.put("/care/dating", headers=auth_headers, json={"current_week": 10}).status_code == 403


def test_dating_by_due_date_and_week_and_it_syncs_the_pregnancy_profile(client: TestClient, auth_headers) -> None:
    client.put("/profile", headers=auth_headers, json={"consent": True, "consent_version": "v1.0"})
    edd = TODAY + timedelta(days=140)  # 20 weeks to go => week 21
    plan = client.put("/care/dating", headers=auth_headers, json={"edd_date": edd.isoformat()}).json()
    assert plan["week"] == 21 and plan["source_of_dates"] == "edd" and plan["edd"] == edd.isoformat()
    pregnancy = client.get("/pregnancy", headers=auth_headers).json()
    assert pregnancy["current_week"] == 21 and pregnancy["trimester"] == 2
    assert client.put("/care/dating", headers=auth_headers, json={"current_week": 8}).json()["week"] == 8
    assert client.put("/care/dating", headers=auth_headers, json={"lmp_date": TODAY.isoformat(), "current_week": 8}).status_code == 422


def test_the_week_moves_forward_without_the_user_doing_anything(client: TestClient, me, monkeypatch) -> None:
    assert client.get("/pregnancy", headers=me).json()["current_week"] == 22
    monkeypatch.setattr(dating, "today_utc", lambda: TODAY + timedelta(days=14))
    assert client.get("/care/plan", headers=me).json()["week"] == 24
    assert client.get("/pregnancy", headers=me).json()["current_week"] == 24  # the older profile row follows


def test_old_week_endpoint_still_works_and_remembers_dates(client: TestClient, auth_headers, monkeypatch) -> None:
    client.put("/profile", headers=auth_headers, json={"consent": True, "consent_version": "v1.0"})
    assert client.put("/pregnancy", headers=auth_headers, json={"current_week": 12, "first_pregnancy": True}).status_code == 200
    monkeypatch.setattr(dating, "today_utc", lambda: TODAY + timedelta(days=28))
    assert client.get("/care/plan", headers=auth_headers).json()["week"] == 16


# ------------------------------------------------------------------------------------------------ plan and reminders
def test_plan_has_visits_supplements_pmsma_and_sources(client: TestClient, me) -> None:
    plan = client.get("/care/plan", headers=me).json()
    assert plan["week"] == 22 and plan["trimester"] == 2 and plan["next_visit"]["week"] == 26
    statuses = {v["week"]: v["status"] for v in plan["visits"]}
    assert statuses[12] == "past" and statuses[20] == "past" and statuses[26] == "upcoming"
    ifa = next(s for s in plan["supplements"] if s["id"] == "ifa")
    folic = next(s for s in plan["supplements"] if s["id"] == "folic_acid")
    assert ifa["active"] and not folic["active"] and "100" in ifa["instruction"]
    assert plan["pmsma"]["date"] == "2026-10-09" and plan["pmsma"]["days_away"] == 8
    assert all(t.get("source") for t in plan["this_week"])
    assert plan["review"] == "pending_clinical_review"


def test_reminders_react_to_what_the_user_has_done(client: TestClient, me) -> None:
    ids = lambda: [r["id"] for r in client.get("/care/reminders", headers=me).json()["reminders"]]  # noqa: E731
    assert {"ifa", "checkin", "hb"} <= set(ids())
    client.put("/care/checkin", headers=me, json={"ifa_taken": True, "mood": 4})
    after = ids()
    assert "ifa" not in after and "checkin" not in after and "hb" in after
    client.post("/care/readings", headers=me, json={"kind": "hb", "value": 11.8})
    assert "hb" not in ids()


# ------------------------------------------------------------------------------------------------ check-in
def test_checkin_round_trip_and_adherence(client: TestClient, me) -> None:
    for back, taken in ((2, True), (1, True), (0, True)):
        day = (TODAY - timedelta(days=back)).isoformat()
        client.put("/care/checkin", headers=me, json={"date": day, "ifa_taken": taken, "mood": 4, "symptoms": ["nausea"]})
    client.put("/care/checkin", headers=me, json={"date": (TODAY - timedelta(days=3)).isoformat(), "ifa_taken": False, "symptoms": ["nausea", "back pain"]})
    got = client.get("/care/checkin", headers=me).json()["checkin"]
    assert got["ifa_taken"] is True and got["triage_level"] == "none"
    s = client.get("/care/checkin/summary?days=14", headers=me).json()
    assert s["ifa_streak"] == 3 and s["ifa_taken"] == 3 and s["ifa_answered"] == 4 and s["ifa_rate"] == 0.75
    assert s["symptom_counts"]["nausea"] == 4


def test_reduced_movement_in_a_checkin_is_a_red_flag(client: TestClient, me) -> None:
    res = client.put("/care/checkin", headers=me, json={"baby_movement": "reduced"}).json()
    assert res["checkin"]["triage_level"] == "urgent" and "reduced_movement" in res["checkin"]["red_flags"]
    assert res["triage"]["level"] == "urgent" and res["triage"]["emergency_numbers"]["general"] == "112"
    assert client.put("/care/checkin", headers=me, json={"baby_movement": "bogus"}).status_code == 422
    assert client.put("/care/checkin", headers=me, json={"date": (TODAY + timedelta(days=1)).isoformat()}).status_code == 422


def test_checkin_requires_consent(client: TestClient, auth_headers) -> None:
    assert client.put("/care/checkin", headers=auth_headers, json={"mood": 3}).status_code == 403


# ------------------------------------------------------------------------------------------------ readings
def test_reading_flags_follow_the_cited_thresholds(client: TestClient, me) -> None:
    low = client.post("/care/readings", headers=me, json={"kind": "hb", "value": 9.8}).json()
    assert low["flags"][0]["level"] == "discuss" and "11" in low["flags"][0]["message"] and low["flags"][0]["url"].startswith("https://www.who.int")
    assert client.post("/care/readings", headers=me, json={"kind": "hb", "value": 11.5}).json()["flags"] == []
    high = client.post("/care/readings", headers=me, json={"kind": "bp", "systolic": 148, "diastolic": 96}).json()
    assert high["flags"][0]["level"] == "urgent" and "today" in high["flags"][0]["message"]
    severe = client.post("/care/readings", headers=me, json={"kind": "bp", "systolic": 168, "diastolic": 112}).json()
    assert "immediately" in severe["flags"][0]["message"]
    assert client.post("/care/readings", headers=me, json={"kind": "bp", "systolic": 120, "diastolic": 80}).json()["flags"] == []
    assert client.post("/care/readings", headers=me, json={"kind": "glucose", "value": 92, "context": "fasting"}).json()["flags"][0]["level"] == "info"


@pytest.mark.parametrize("body", [
    {"kind": "hb", "value": 0.5}, {"kind": "hb"}, {"kind": "bp", "systolic": 120}, {"kind": "bp", "systolic": 80, "diastolic": 120},
    {"kind": "weight", "value": 5}, {"kind": "hb", "value": 11, "date": (TODAY + timedelta(days=30)).isoformat()}, {"kind": "pulse", "value": 70},
])
def test_implausible_readings_are_rejected(client: TestClient, me, body) -> None:
    assert client.post("/care/readings", headers=me, json=body).status_code in (422, 400)


def test_urgent_reading_is_recorded_as_a_safety_event(client: TestClient, me, admin_headers) -> None:
    client.post("/care/readings", headers=me, json={"kind": "bp", "systolic": 150, "diastolic": 100})
    events = client.get("/admin/safety-events", headers=admin_headers).json()
    assert any(e["action"] == "reading_flag" for e in events)


def test_list_delete_and_weight_gain(client: TestClient, me) -> None:
    client.post("/care/readings", headers=me, json={"kind": "weight", "value": 58.5, "date": (TODAY - timedelta(days=30)).isoformat()})
    last = client.post("/care/readings", headers=me, json={"kind": "weight", "value": 61.0}).json()
    body = client.get("/care/readings?kind=weight", headers=me).json()
    assert [r["value"] for r in body["readings"]] == [58.5, 61.0]
    gain = body["weight_gain"]
    assert gain["baseline"] == "pre-pregnancy weight" and gain["gain_kg"] == 6.0 and gain["healthy_total_gain_kg"] == [10, 12]
    assert client.delete(f"/care/readings/{last['id']}", headers=me).status_code == 200
    assert client.delete(f"/care/readings/{last['id']}", headers=me).status_code == 404


def test_report_text_is_parsed_into_candidates_not_saved(client: TestClient, me) -> None:
    text = "Date: 12/09/2026\nHb: 10.2 g/dL\nBP 118/76 mmHg\nWeight 62.5 kg\nFasting blood sugar 88 mg/dL\nTSH 2.1"
    c = client.post("/care/readings/parse-report", headers=me, json={"text": text}).json()["candidates"]
    by = {x["kind"]: x for x in c}
    assert by["hb"]["value"] == 10.2 and by["bp"]["systolic"] == 118 and by["weight"]["value"] == 62.5
    assert by["glucose"]["value"] == 88 and by["glucose"]["context"] == "fasting" and by["hb"]["date"] == "2026-09-12"
    assert client.get("/care/readings", headers=me).json()["readings"] == []  # nothing saved until the user confirms


def test_report_parsing_handles_units_and_rejects_nonsense() -> None:
    assert readings.parse_report_text("Haemoglobin 105 g/L")[0]["value"] == 10.5
    assert readings.parse_report_text("Hb 4000") == []  # out of range
    assert readings.parse_report_text("nothing useful here") == []


def test_photo_reading_falls_back_gracefully(client: TestClient, me, monkeypatch) -> None:
    monkeypatch.setattr(readings.shutil, "which", lambda _: None)
    r = client.post("/care/readings/ocr", headers=me, files={"file": ("r.png", b"\x89PNG", "image/png")})
    assert r.status_code == 501 and "Paste the report text" in r.json()["detail"]
    assert client.post("/care/readings/ocr", headers=me, files={"file": ("r.txt", b"hello", "text/plain")}).status_code == 422


# ------------------------------------------------------------------------------------------------ meals
def test_meal_parser_understands_everyday_portions() -> None:
    p = meals.parse_meal("2 roti, 1 katori dal, curd, a banana and 1 glass milk, some pizza")
    by = {i["name"]: i for i in p["items"]}
    assert by["Whole wheat flour (atta)"]["grams"] == 60 and by["Lentils (masoor dal)"]["grams"] == 150
    assert by["Milk (2% fat)"]["grams"] == 250 and by["Banana (kela)"]["grams"] == 100 and by["Plain yogurt (dahi / curd)"]["grams"] == 150
    assert p["unknown"] == ["some pizza"] and all(i["approximate"] for i in p["items"])
    assert meals.parse_meal("zzz qqq")["items"] == []


def test_meal_endpoint_totals_and_gaps(client: TestClient, me) -> None:
    res = client.post("/care/meals", headers=me, json={"text": "2 roti, 1 katori dal, curd", "meal_type": "lunch"}).json()
    assert res["totals"]["protein"] > 20 and res["not_understood"] == []
    day = client.get("/care/meals", headers=me).json()
    assert len(day["meals"]) == 1 and day["totals"]["iron"] > 0
    rows = {r["nutrient"]: r for r in day["rows"]}
    assert rows["iron"]["target"] == 27 and rows["iron"]["percent"] < 70 and day["suggestions"]
    names = " ".join(f["name"] for s in day["suggestions"] for f in s["foods"]).lower()
    assert "liver" not in names and "chicken" not in names and "salmon" not in names  # vegetarian, and no liver in pregnancy
    assert "peanut" not in names  # the user's allergy
    assert client.post("/care/meals", headers=me, json={"text": "pizza and burger"}).status_code == 422
    mid = day["meals"][0]["id"]
    assert client.delete(f"/care/meals/{mid}", headers=me).status_code == 200 and client.get("/care/meals", headers=me).json()["meals"] == []


# ------------------------------------------------------------------------------------------------ screening
def test_triage_takes_the_most_serious_yes() -> None:
    assert screening.assess({"heavy_bleeding": True, "low_mood": True}, 22)["level"] == "emergency"
    assert screening.assess({"reduced_movement": True, "low_mood": True}, 22)["level"] == "urgent"
    assert screening.assess({"low_mood": True}, 22)["level"] == "soon"
    assert screening.assess({"low_mood": False, "fever": False}, 22)["level"] == "none"
    assert screening.assess({}, 22)["level"] == "none"


def test_questions_respect_the_week_and_ignore_unknown_ids() -> None:
    early = {q["id"] for q in screening.questions_for(8)}
    late = {q["id"] for q in screening.questions_for(34)}
    assert "reduced_movement" not in early and "reduced_movement" in late
    assert "sickness_daily_life" in early and "sickness_daily_life" not in late
    assert screening.assess({"made_up": True, "reduced_movement": True}, 8)["level"] == "none"  # not asked at week 8
    assert all(q["source"] and q["url"].startswith("https://") for q in screening.questions_for(30))
    assert [q["level"] for q in screening.questions_for(30)] == sorted((q["level"] for q in screening.questions_for(30)), key=screening.ORDER.index)


def test_screening_endpoint_records_and_gives_a_way_to_get_help(client: TestClient, me, admin_headers) -> None:
    client.put("/care/emergency-contact", headers=me, json={"name": "Ravi", "phone": "+91 98765 43210", "relation": "husband"})
    qs = client.get("/care/screening/questions", headers=me).json()
    assert qs["week"] == 22 and any(q["id"] == "severe_headache" for q in qs["questions"])
    res = client.post("/care/screening/assess", headers=me, json={"answers": {"severe_headache": True, "vision": True, "heavy_bleeding": False}}).json()
    assert res["level"] == "urgent" and {f["id"] for f in res["flagged"]} == {"severe_headache", "vision"}
    assert res["contact"]["name"] == "Ravi" and "google.com/maps" in res["maps_url"] and res["emergency_numbers"]["ambulance"] == ["108", "102"]
    assert any(e["action"] == "screening" for e in client.get("/admin/safety-events", headers=admin_headers).json())
    assert client.post("/care/screening/assess", headers=me, json={"answers": {"heavy_bleeding": True}}).json()["level"] == "emergency"


def test_emergency_contact_validation(client: TestClient, me) -> None:
    assert client.put("/care/emergency-contact", headers=me, json={"name": "A", "phone": "abc"}).status_code == 422
    assert client.put("/care/emergency-contact", headers=me, json={"name": "Asha", "phone": "9876543210"}).status_code == 200
    assert client.get("/care/emergency-contact", headers=me).json()["contact"]["phone"] == "9876543210"
    assert client.delete("/care/emergency-contact", headers=me).status_code == 200
    assert client.get("/care/emergency-contact", headers=me).json()["contact"] is None


# ------------------------------------------------------------------------------------------------ summary and privacy
def test_doctor_summary_collects_everything_and_proposes_questions(client: TestClient, me) -> None:
    client.post("/care/readings", headers=me, json={"kind": "hb", "value": 9.9})
    client.post("/care/readings", headers=me, json={"kind": "weight", "value": 60})
    for back in range(4):
        client.put("/care/checkin", headers=me, json={"date": (TODAY - timedelta(days=back)).isoformat(), "ifa_taken": back == 0, "symptoms": ["back pain"]})
    client.post("/care/meals", headers=me, json={"text": "rice, dal"})
    s = client.get("/care/summary", headers=me).json()
    assert s["pregnancy"]["week"] == 22 and s["readings"]["latest"]["hb"]["value"] == 9.9
    assert s["iron_tablets"]["ifa_taken"] == 1 and s["symptoms_last_14_days"]["back pain"] == 4 and s["nutrition"]["days_logged"] == 1
    joined = " ".join(s["questions_for_doctor"])
    assert "haemoglobin was 9.9" in joined and "iron tablet on 1 of 4" in joined and "back pain on 4" in joined
    assert "not a medical record" in s["disclaimer"]


def test_withdrawing_consent_deletes_all_care_data_and_export_includes_it(client: TestClient, me) -> None:
    client.put("/care/checkin", headers=me, json={"mood": 3})
    client.post("/care/readings", headers=me, json={"kind": "hb", "value": 12})
    client.post("/care/meals", headers=me, json={"text": "rice"})
    exported = client.get("/privacy/export", headers=me).json()["care"]
    assert exported["daily_checkins"] and exported["health_readings"] and exported["meal_logs"] and exported["pregnancy_dating"]
    assert client.post("/privacy/consent", headers=me, json={"granted": False, "version": "v1.0"}).status_code == 200
    after = client.get("/privacy/export", headers=me).json()["care"]
    assert all(rows == [] for rows in after.values())
    assert client.get("/care/readings", headers=me).json()["readings"] == []


def test_every_endpoint_requires_sign_in(client: TestClient) -> None:
    for method, path in (("get", "/care/plan"), ("get", "/care/reminders"), ("put", "/care/checkin"), ("get", "/care/readings"),
                         ("get", "/care/meals"), ("post", "/care/screening/assess"), ("get", "/care/summary"), ("put", "/care/dating")):
        assert getattr(client, method)(path).status_code in (401, 403, 422), path


def test_care_rules_are_complete_and_every_rule_names_its_source() -> None:
    from app.services.care.rules import foods, rules

    r = rules()
    assert all(q["source"] and q["url"] for q in r["screening"]["questions"])
    assert all(c.get("source") for c in r["readings"].values()) and all(s["source"] for s in r["supplements"])
    assert {a["food"] for a in r["food_aliases"].values()} <= set(foods())
    assert r["nutrition_targets"]["review"] == "pending_clinical_review" and r["visit_schedule"]["review"] == "pending_clinical_review"


# ------------------------------------------------------------------------------------------------ chat statements
def test_chat_records_a_reading_and_explains_it(client: TestClient, me) -> None:
    res = client.post("/chat", headers=me, json={"message": "My Hb is 9.8 today"}).json()
    assert "Recorded your haemoglobin: 9.8 g/dL" in res["answer"] and "anaemia" in res["answer"] and res["sources"] == []
    assert client.get("/care/readings?kind=hb", headers=me).json()["readings"][0]["source"] == "chat"
    bp = client.post("/chat", headers=me, json={"message": "my BP was 150/100 this morning"}).json()
    assert "150/100" in bp["answer"] and "today" in bp["answer"] and "/check" in bp["answer"]


def test_a_question_about_a_reading_is_not_logged(client: TestClient, me) -> None:
    client.post("/chat", headers=me, json={"message": "Is a Hb of 9.8 normal in pregnancy?"})
    assert client.get("/care/readings", headers=me).json()["readings"] == []


def test_chat_logs_a_meal_and_reports_gaps(client: TestClient, me) -> None:
    res = client.post("/chat", headers=me, json={"message": "I had 2 roti and 1 katori dal for lunch"}).json()
    assert res["answer"].startswith("Logged") and "protein" in res["answer"] and "approximate" in res["answer"]
    assert len(client.get("/care/meals", headers=me).json()["meals"]) == 1
    assert client.post("/chat", headers=me, json={"message": "What should I have for lunch?"}).json()["answer"].startswith("Logged") is False


def test_without_consent_chat_does_not_store_health_numbers(client: TestClient, auth_headers) -> None:
    client.post("/chat", headers=auth_headers, json={"message": "My Hb is 9.8 today"})
    assert client.get("/care/readings", headers=auth_headers).json()["readings"] == []


def test_a_dating_row_with_no_dates_falls_back_to_the_plain_week_instead_of_crashing(client: TestClient, auth_headers) -> None:
    """A row with neither a last period nor a due date used to raise a TypeError (None minus a timedelta)."""
    from app.core.db import SessionLocal
    from app.models import PregnancyDating, User

    client.put("/profile", headers=auth_headers, json={"consent": True, "consent_version": "v1.0"})
    client.put("/pregnancy", headers=auth_headers, json={"current_week": 12, "first_pregnancy": True})
    with SessionLocal() as db:
        user = db.query(User).one()
        row = db.query(PregnancyDating).filter_by(user_id=user.id).one_or_none() or PregnancyDating(user_id=user.id, source="week")
        row.lmp_date = row.edd_date = None
        db.add(row)
        db.commit()
        d = dating.resolve(db, user, TODAY)
        assert d is not None and d.week == 12


def test_week_fallback_does_not_regress_if_profile_timestamp_is_in_the_future(client: TestClient, auth_headers) -> None:
    from app.core.db import SessionLocal
    from app.models import PregnancyDating, PregnancyProfile, User

    client.put("/profile", headers=auth_headers, json={"consent": True, "consent_version": "v1.0"})
    client.put("/pregnancy", headers=auth_headers, json={"current_week": 12, "first_pregnancy": True})
    with SessionLocal() as db:
        user = db.query(User).one()
        row = db.query(PregnancyDating).filter_by(user_id=user.id).one_or_none() or PregnancyDating(user_id=user.id, source="week")
        row.lmp_date = row.edd_date = None
        profile = db.query(PregnancyProfile).filter_by(user_id=user.id).one()
        profile.updated_at = datetime.combine(TODAY + timedelta(days=1), time.min, tzinfo=timezone.utc)
        db.add_all([row, profile])
        db.commit()
        d = dating.resolve(db, user, TODAY)
        assert d is not None and d.week == 12
