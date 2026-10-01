"""Daily check-ins, iron-tablet adherence and reminders."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyCheckin, HealthReading, User
from app.services.care import plan as plan_module
from app.services.care.dating import Dating
from app.services.care.rules import rules
from app.services.care.screening import red_flag_level

SYMPTOMS = ["nausea", "vomiting", "headache", "back pain", "swelling", "heartburn", "constipation", "tiredness", "cramps", "dizziness", "leg cramps", "poor sleep"]
MOVEMENT = {"normal", "reduced", "not_yet"}


def get_checkin(db: Session, user: User, day: date) -> DailyCheckin | None:
    return db.execute(select(DailyCheckin).where(DailyCheckin.user_id == user.id, DailyCheckin.check_date == day)).scalar_one_or_none()


def upsert_checkin(
    db: Session, user: User, day: date, *, mood: int | None, symptoms: list[str], baby_movement: str | None,
    ifa_taken: bool | None, note: str | None, red_flags: list[str],
) -> DailyCheckin:
    row = get_checkin(db, user, day) or DailyCheckin(user_id=user.id, check_date=day)
    row.mood = mood
    row.symptoms = symptoms
    row.baby_movement = baby_movement
    row.ifa_taken = ifa_taken
    row.note = note
    row.red_flags = red_flags
    db.add(row)
    db.flush()
    return row


def checkin_payload(row: DailyCheckin | None, week: int | None) -> dict[str, Any] | None:
    if row is None:
        return None
    flags = list(row.red_flags or [])
    if row.baby_movement == "reduced" and "reduced_movement" not in flags:
        flags.append("reduced_movement")  # saying movements are reduced IS the red flag
    level = red_flag_level(flags, week) if flags else "none"
    return {
        "date": row.check_date.isoformat(), "mood": row.mood, "symptoms": row.symptoms or [], "baby_movement": row.baby_movement,
        "ifa_taken": row.ifa_taken, "note": row.note, "red_flags": flags, "triage_level": level,
    }


def adherence(db: Session, user: User, today: date, days: int = 14) -> dict[str, Any]:
    """Iron-tablet adherence over the last `days` days, counting only days the user checked in."""
    start = today - timedelta(days=days - 1)
    rows = db.execute(select(DailyCheckin).where(DailyCheckin.user_id == user.id, DailyCheckin.check_date >= start).order_by(DailyCheckin.check_date)).scalars().all()
    answered = [r for r in rows if r.ifa_taken is not None]
    taken = sum(1 for r in answered if r.ifa_taken)
    streak = 0
    by_day = {r.check_date: r for r in rows}
    d = today
    while d in by_day and by_day[d].ifa_taken:
        streak += 1
        d -= timedelta(days=1)
    return {
        "days": days, "checked_in": len(rows), "ifa_answered": len(answered), "ifa_taken": taken,
        "ifa_rate": round(taken / len(answered), 2) if answered else None, "ifa_streak": streak,
        "symptom_counts": _count([s for r in rows for s in (r.symptoms or [])]),
        "mood_average": round(sum(r.mood for r in rows if r.mood) / max(1, sum(1 for r in rows if r.mood)), 1) if any(r.mood for r in rows) else None,
    }


def _count(items: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def reminders(db: Session, user: User, d: Dating, today: date) -> list[dict[str, Any]]:
    """What needs attention today, most important first. Pure rules over the user's own records."""
    items: list[dict[str, Any]] = []
    checkin = get_checkin(db, user, today)
    plan = plan_module.build_plan(d, today)

    ifa = next((s for s in plan["supplements"] if s["id"] == "ifa" and s["active"]), None)
    if ifa and not (checkin and checkin.ifa_taken):
        items.append({"id": "ifa", "priority": 1, "title": "Iron + folic acid tablet", "detail": ifa["instruction"], "action": "checkin", "kind": "supplement"})
    nxt = plan["next_visit"]
    if nxt and nxt["days_away"] <= 7:
        when = "now" if nxt["status"] == "due_now" else f"in {max(nxt['days_away'], 0)} day(s)"
        items.append({"id": "visit", "priority": 2, "title": f"Antenatal visit {when}", "detail": f"Around week {nxt['week']}. Bring your records: open the doctor summary.", "action": "summary", "kind": "visit"})
    pm = plan["pmsma"]
    if pm and pm["days_away"] <= 3:
        items.append({"id": "pmsma", "priority": 3, "title": "Free PMSMA check-up on the 9th", "detail": pm["note"], "action": None, "kind": "visit"})
    if checkin is None:
        items.append({"id": "checkin", "priority": 4, "title": "Today's check-in", "detail": "Thirty seconds: how you feel, baby's movements, your tablet.", "action": "checkin", "kind": "checkin"})
    hb = db.execute(select(HealthReading).where(HealthReading.user_id == user.id, HealthReading.kind == "hb").order_by(HealthReading.reading_date.desc())).scalars().first()
    if d.week >= 12 and (hb is None or (today - hb.reading_date).days > 84):
        items.append({"id": "hb", "priority": 5, "title": "Haemoglobin check", "detail": "No haemoglobin recorded in the last 12 weeks. Ask for the test at your next visit and add the result here.", "action": "readings", "kind": "readings"})
    items.sort(key=lambda r: r["priority"])
    return items
