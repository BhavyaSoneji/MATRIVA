"""The one-page summary a woman can show her doctor: dates, readings, symptoms, tablets, flags and questions to ask."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyCheckin, DietaryProfile, HealthProfile, MealLog, ScreeningRecord, User
from app.services.care import meals as meals_module
from app.services.care import readings as readings_module
from app.services.care import tracking
from app.services.care.dating import Dating, resolve
from app.services.care.plan import build_plan

WINDOW_DAYS = 14


def _latest(rows, kind):
    r = [x for x in rows if x.kind == kind]
    return r[-1] if r else None


def build(db: Session, user: User, today: date) -> dict[str, Any]:
    d: Dating | None = resolve(db, user, today)
    rows = readings_module.history(db, user, days=365, today=today)
    health = db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id)).scalar_one_or_none()
    diet = db.execute(select(DietaryProfile).where(DietaryProfile.user_id == user.id)).scalar_one_or_none()
    adherence = tracking.adherence(db, user, today, WINDOW_DAYS)

    latest = {}
    for kind in readings_module.KINDS:
        r = _latest(rows, kind)
        if r:
            latest[kind] = readings_module.payload(r)
    trend = {k: [readings_module.payload(r) for r in rows if r.kind == k][-6:] for k in readings_module.KINDS}

    since = today - timedelta(days=WINDOW_DAYS - 1)
    checkins = list(db.execute(select(DailyCheckin).where(DailyCheckin.user_id == user.id, DailyCheckin.check_date >= since).order_by(DailyCheckin.check_date)).scalars().all())
    red_flags = [{"date": c.check_date.isoformat(), "flags": tracking.checkin_payload(c, d.week if d else None)["red_flags"]}
                 for c in checkins if (c.red_flags or c.baby_movement == "reduced")]
    screening = db.execute(select(ScreeningRecord).where(ScreeningRecord.user_id == user.id).order_by(ScreeningRecord.created_at.desc())).scalars().first()

    meal_rows = list(db.execute(select(MealLog).where(MealLog.user_id == user.id, MealLog.meal_date >= since)).scalars().all())
    nutrition = None
    if meal_rows:
        per_day: dict[date, dict[str, float]] = {}
        for m in meal_rows:
            for k, v in (m.totals or {}).items():
                per_day.setdefault(m.meal_date, {})[k] = per_day.get(m.meal_date, {}).get(k, 0.0) + v
        avg = {k: round(sum(day.get(k, 0.0) for day in per_day.values()) / len(per_day), 1) for k in meals_module.GAP_NUTRIENTS}
        nutrition = {"days_logged": len(per_day), "average_per_day": avg, **meals_module.gaps(avg, diet.diet_type if diet else None)}

    questions = _questions(latest, adherence, red_flags, d)
    return {
        "generated_on": today.isoformat(),
        "name": user.full_name,
        "pregnancy": None if d is None else {
            "week": d.week, "day": d.day, "trimester": d.trimester, "edd": d.edd.isoformat(), "lmp": d.lmp.isoformat(),
            "dates_from": d.source, "next_visit": build_plan(d, today)["next_visit"],
        },
        "health": {
            "known_conditions": health.known_conditions if health else [], "allergies": health.allergies if health else [],
            "current_medications": (health.current_medications or []) if health else [],
            "risk_factors": (health.risk_factors or []) if health else [],
            "blood_group": health.blood_group if health else None, "age_years": health.age_years if health else None,
            "doctor_restrictions": health.doctor_restrictions if health else [], "diet": diet.diet_type if diet else None,
        },
        "readings": {"latest": latest, "trend": trend, "weight_gain": readings_module.weight_gain(rows, d)},
        "iron_tablets": adherence, "symptoms_last_14_days": adherence["symptom_counts"], "red_flags": red_flags,
        "last_screening": None if screening is None else {"date": screening.created_at.date().isoformat(), "level": screening.level, "flagged": screening.flagged},
        "nutrition": nutrition, "questions_for_doctor": questions,
        "disclaimer": "Prepared from information the patient entered. It is not a medical record or a diagnosis; please verify with your own tests.",
    }


def _questions(latest: dict, adherence: dict, red_flags: list, d: Dating | None) -> list[str]:
    q: list[str] = []
    hb = latest.get("hb")
    if hb and hb["flags"]:
        q.append(f"My haemoglobin was {hb['value']} g/dL on {hb['date']}. Should my iron treatment change, and when should it be rechecked?")
    bp = latest.get("bp")
    if bp and bp["flags"]:
        q.append(f"My blood pressure was {bp['systolic']}/{bp['diastolic']} on {bp['date']}. Do I need extra checks for pre-eclampsia?")
    if adherence["ifa_answered"] and adherence["ifa_rate"] is not None and adherence["ifa_rate"] < 0.8:
        q.append(f"I took my iron tablet on {adherence['ifa_taken']} of {adherence['ifa_answered']} days. Is there an alternative if it upsets my stomach?")
    for symptom, n in list(adherence["symptom_counts"].items())[:3]:
        if n >= 3:
            q.append(f"I noted {symptom} on {n} of the last {adherence['days']} days. Is that expected, and what can I do?")
    if red_flags:
        q.append(f"I reported warning signs on {len(red_flags)} day(s) recently. Please review them.")
    if d:
        q.append("Which tests or scans are due before my next visit?")
    return q
