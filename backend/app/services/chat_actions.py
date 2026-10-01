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

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.api import WellnessLogRequest
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
