"""Actions the chat can perform from plain first-person statements.

"I drank 3 glasses of water and slept 7 hours" updates today's wellness log -- no model
involved, so it is deterministic and cannot misread a number into a different action.
Questions ("how many glasses should I drink?") never match: a statement needs a past-tense
verb ("drank", "slept", "walked"), and anything containing a question mark is left to the
normal answer path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.api import WellnessLogRequest
from app.services.care.rules import rules
from app.services.wellness import get_daily_log, upsert_daily_log

ML_PER_GLASS = 250
_NUM = r"(\d+(?:\.\d+)?|a|one|two|three|four|five|six|seven|eight|nine|ten)"
_WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

_WATER_RE = re.compile(
    rf"\b(?:drank|had|finished|drunk)\s+(?:about\s+|around\s+)?{_NUM}\s*(glass(?:es)?|cups?|bottles?|litres?|liters?|ml|l)\b(?:\s+of\s+water)?",
    re.IGNORECASE,
)
_SLEEP_RE = re.compile(rf"\bslept\s+(?:for\s+|about\s+|around\s+)?{_NUM}\s*(?:hours?|hrs?|h)\b", re.IGNORECASE)
_ACTIVITY_RE = re.compile(
    rf"\b(?:walked|exercised|jogged|swam|worked out|did (?:some )?(?:yoga|stretching|exercise|pilates))\b[^.?!\d]{{0,30}}?(\d+)\s*(?:minutes?|mins?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChatActionResult:
    summary: str  # user-facing confirmation


def _to_number(raw: str) -> float:
    return float(_WORDS.get(raw.lower(), raw)) if not raw.replace(".", "", 1).isdigit() else float(raw)


def _water_ml(amount: float, unit: str) -> float:
    unit = unit.lower()
    if unit == "ml":
        return amount
    if unit in {"l", "litre", "litres", "liter", "liters"}:
        return amount * 1000
    if unit.startswith("bottle"):
        return amount * 500
    return amount * ML_PER_GLASS


def parse_wellness_statement(message: str) -> WellnessLogRequest | None:
    """Pull water / sleep / activity out of a first-person statement, or None if there is none."""
    if "?" in message or len(message) > 300:
        return None
    water = _WATER_RE.search(message)
    sleep = _SLEEP_RE.search(message)
    activity = _ACTIVITY_RE.search(message)
    if not (water or sleep or activity):
        return None
    payload: dict[str, float | int] = {}
    if water:
        ml = _water_ml(_to_number(water.group(1)), water.group(2))
        if 0 < ml <= 10000:
            payload["water_intake_ml"] = ml
    if sleep:
        hours = _to_number(sleep.group(1))
        if 0 < hours <= 24:
            payload["sleep_hours"] = hours
    if activity:
        minutes = int(activity.group(1))
        if 0 < minutes <= 1440:
            payload["activity_minutes"] = minutes
    return WellnessLogRequest(**payload) if payload else None


def apply_wellness_statement(db: Session, user: User, message: str) -> ChatActionResult | None:
    """Log water and activity additively (several messages add up through the day) and set sleep.

    Returns None when the message is not a loggable statement.
    """
    parsed = parse_wellness_statement(message)
    if parsed is None:
        return None
    from datetime import datetime, timezone

    existing = get_daily_log(db, user, datetime.now(timezone.utc).date())
    update = WellnessLogRequest(
        water_intake_ml=(
            (existing.water_intake_ml or 0) + parsed.water_intake_ml if parsed.water_intake_ml is not None else None
        ),
        sleep_hours=parsed.sleep_hours,
        activity_minutes=(
            (existing.activity_minutes or 0) + parsed.activity_minutes if parsed.activity_minutes is not None else None
        ),
    ) if existing else parsed
    log = upsert_daily_log(db, user, update)

    parts = []
    if parsed.water_intake_ml is not None:
        parts.append(f"{round(parsed.water_intake_ml)} ml of water (today: {round(log.water_intake_ml or 0)} ml)")
    if parsed.sleep_hours is not None:
        parts.append(f"{parsed.sleep_hours:g} hours of sleep")
    if parsed.activity_minutes is not None:
        parts.append(f"{parsed.activity_minutes} minutes of activity (today: {log.activity_minutes} min)")
    return ChatActionResult(summary="Logged " + ", ".join(parts) + ". Open /log to see your week.")


# ----------------------------------------------------------------------------------------------- readings and meals
_READING_CUE = re.compile(r"\b(?:my|today|was|is|came|checked|measured|report|reading|got)\b", re.I)
_MEAL_RE = re.compile(r"\b(?:i|we)\s+(?:just\s+)?(?:ate|had|have eaten|eaten|am eating|was eating)\b(?P<food>[^.?!]{3,200})", re.I)


def apply_reading_statement(db: Session, user: User, message: str) -> ChatActionResult | None:
    """"My Hb is 10.2" / "BP was 120/80 today": record it, and say plainly what it means (or that it needs a doctor)."""
    if "?" in message or len(message) > 200 or not _READING_CUE.search(message):
        return None
    from app.services.care import readings as readings_module
    from app.services.profile import has_consent

    candidates = readings_module.parse_report_text(message)
    if not candidates or not has_consent(db, user.id):
        return None
    lines, urgent = [], False
    for c in candidates[:3]:
        row = readings_module.add(
            db, user, c["kind"], date.fromisoformat(c["date"]), value=c.get("value"), systolic=c.get("systolic"),
            diastolic=c.get("diastolic"), context=c.get("context"), source="chat",
        )
        out = readings_module.payload(row)
        what = f"{out['systolic']}/{out['diastolic']} mmHg" if row.kind == "bp" else f"{out['value']:g} {out['unit']}"
        label = rules()["readings"][row.kind]["label"].lower()
        lines.append(f"Recorded your {label}: {what}.")
        for flag in out["flags"]:
            lines.append(flag["message"])
            urgent = urgent or flag["level"] == "urgent"
    if urgent:
        lines.append("This needs attention today: open /check for a quick safety check, or call your doctor or 112.")
    return ChatActionResult(summary=" ".join(lines) + " See your trend with /readings.")


def apply_meal_statement(db: Session, user: User, message: str) -> ChatActionResult | None:
    """"I had 2 roti and dal for lunch": log it and show how it adds up for the day."""
    if "?" in message or len(message) > 300:
        return None
    m = _MEAL_RE.search(message)
    if not m:
        return None
    from app.services.care import dating as dating_module
    from app.services.care import meals as meals_module
    from app.services.profile import has_consent

    if not has_consent(db, user.id):
        return None
    day = dating_module.today_utc()
    row, parsed = meals_module.log(db, user, day, m.group("food"))
    if row is None:
        return None
    _, totals = meals_module.day_totals(db, user, day)
    gaps = meals_module.gaps(totals)
    low = [r for r in gaps["rows"] if r["percent"] < 50][:2]
    said = ", ".join(f"{i['name'].split(' (')[0].lower()} ({i['grams']:g} g)" for i in row.items)
    text = f"Logged {said}. About {row.totals.get('protein', 0):.0f} g protein and {row.totals.get('iron', 0):.1f} mg iron in this meal."
    if low:
        text += " So far today you are low on " + " and ".join(r["nutrient"] for r in low) + " (see /meals for ideas)."
    if parsed["unknown"]:
        text += " I did not recognise: " + "; ".join(parsed["unknown"]) + "."
    return ChatActionResult(summary=text + " Portions are approximate.")


def apply_any_statement(db: Session, user: User, message: str) -> ChatActionResult | None:
    """The first of: water/sleep/activity, a health reading, a meal."""
    return (
        apply_wellness_statement(db, user, message)
        or apply_reading_statement(db, user, message)
        or apply_meal_statement(db, user, message)
    )
