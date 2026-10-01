from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models import User
from app.rag.followup import looks_like_followup, resolve_followup
from app.services.chat_actions import parse_wellness_statement
from app.services.suggestions import suggest_followups

# ---- follow-up resolution -------------------------------------------------


def test_short_followup_gets_the_previous_topic() -> None:
    assert resolve_followup("what about ragi?", ["Which foods are rich in calcium?"]) == (
        "Which foods are rich in calcium? what about ragi?"
    )
    assert "iron" in resolve_followup("is it safe?", ["How much iron do I need?"])


def test_standalone_question_is_left_alone() -> None:
    q = "Which vitamins should I take during the second trimester?"
    assert resolve_followup(q, ["How much caffeine is okay?"]) == q


def test_no_history_means_no_change_and_followup_cues() -> None:
    assert resolve_followup("what about ragi?", []) == "what about ragi?"
    assert looks_like_followup("and curd?")
    assert not looks_like_followup("What are the signs of pre-eclampsia in the third trimester?")


# ---- wellness statements --------------------------------------------------


def test_parses_water_sleep_and_activity() -> None:
    p = parse_wellness_statement("I drank 3 glasses of water and slept 7.5 hours, walked for 20 minutes")
    assert p is not None
    assert p.water_intake_ml == 750 and p.sleep_hours == 7.5 and p.activity_minutes == 20


def test_word_numbers_and_units() -> None:
    assert parse_wellness_statement("I drank two litres of water").water_intake_ml == 2000
    assert parse_wellness_statement("had a bottle of water").water_intake_ml == 500


def test_questions_and_non_statements_are_not_logged() -> None:
    assert parse_wellness_statement("How many glasses of water should I drink?") is None
    assert parse_wellness_statement("I slept 7 hours, is that enough?") is None
    assert parse_wellness_statement("What foods help me sleep 8 hours") is None
    assert parse_wellness_statement("I drank 99999 glasses of water") is None


def test_chat_logs_wellness_and_accumulates_water(client: TestClient, auth_headers: dict[str, str]) -> None:
    first = client.post("/chat", headers=auth_headers, json={"message": "I drank 2 glasses of water"}).json()
    assert "Logged 500 ml" in first["answer"] and first["sources"] == []
    assert first["suggestions"] == [] and first["recommendations"] == []  # a confirmation, not a topic to follow up on
    second = client.post("/chat", headers=auth_headers, json={"message": "I drank 1 glass of water and slept 8 hours"}).json()
    assert "today: 750 ml" in second["answer"]
    log = client.get("/wellness/daily", headers=auth_headers).json()
    assert log["water_intake_ml"] == 750 and log["sleep_hours"] == 8


def test_urgent_message_is_never_treated_as_a_log(client: TestClient, auth_headers: dict[str, str]) -> None:
    res = client.post("/chat", headers=auth_headers, json={"message": "I drank water and have heavy bleeding"}).json()
    assert res["safety_status"] == "urgent_escalation"
    assert client.get("/wellness/daily", headers=auth_headers).status_code == 404


# ---- suggestions ----------------------------------------------------------


def test_suggestions_are_stage_aware_and_skip_asked_questions() -> None:
    s = suggest_followups("NUTRITION", "third_trimester", asked=["Which foods should I avoid?"])
    assert s[0] == "What are the signs of labour?"
    assert "Which foods should I avoid?" not in s and len(s) == 3
    assert suggest_followups("UNKNOWN_INTENT", None)  # falls back to general starters


def test_chat_returns_suggestions(client: TestClient, auth_headers: dict[str, str]) -> None:
    res = client.post("/chat", headers=auth_headers, json={"message": "Which foods should I eat for iron?"}).json()
    assert len(res["suggestions"]) == 3


# ---- personalisation + follow-ups end to end ------------------------------


def _profile(client: TestClient, headers: dict[str, str]) -> None:
    client.put("/profile", headers=headers, json={
        "consent": True, "consent_version": "v1.0", "full_name": "Asha Verma", "allergies": ["peanuts"],
        "known_conditions": ["anaemia"], "diet_type": "vegetarian", "language": "hi",
    })
    client.put("/pregnancy", headers=headers, json={"current_week": 30, "first_pregnancy": True})


def test_user_context_includes_health_details_only_with_consent(client: TestClient, auth_headers: dict[str, str]) -> None:
    from app.services.personalization import build_user_context

    _profile(client, auth_headers)
    with SessionLocal() as db:
        user = db.query(User).one()
        ctx = build_user_context(db, user)
        text = " | ".join(ctx.profile_notes)
        assert "week 30" in text and "vegetarian" in text and "peanuts" in text and "anaemia" in text
        assert "Asha" not in text  # names are never sent
        assert ctx.reply_language == "Hindi"
        assert build_user_context(db, user, "gu").reply_language == "Gujarati"

    client.delete("/profile", headers=auth_headers)  # revokes the stored health profile
    with SessionLocal() as db:
        ctx = build_user_context(db, db.query(User).one())
        assert "peanuts" not in " | ".join(ctx.profile_notes)


def test_followup_question_uses_previous_turn_in_chat(client: TestClient, auth_headers: dict[str, str], monkeypatch) -> None:
    seen: list[str] = []
    import app.services.chat as chat_module

    real = chat_module.answer_question

    def spy(db, query, **kwargs):
        seen.append(query)
        return real(db, query, **kwargs)

    monkeypatch.setattr(chat_module, "answer_question", spy)
    first = client.post("/chat", headers=auth_headers, json={"message": "Which foods are rich in calcium for pregnancy?"}).json()
    client.post("/chat", headers=auth_headers, json={"message": "what about ragi?", "conversation_id": first["conversation_id"]})
    assert seen[-1].startswith("Which foods are rich in calcium for pregnancy?") and seen[-1].endswith("what about ragi?")


def test_language_field_is_validated(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.post("/chat", headers=auth_headers, json={"message": "hello there friend", "language": "xx"}).status_code == 422
