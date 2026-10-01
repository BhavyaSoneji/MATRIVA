"""Structured red-flag screening.

A short yes/no questionnaire instead of hoping a keyword is spotted in free text. Every question carries its source; the
triage level is the most serious level among the questions answered "yes". The questions, levels and wording are in
app/data/care_rules.yaml and are marked pending clinical review.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import ScreeningRecord, User
from app.services.care.rules import rules

ORDER = ["emergency", "urgent", "soon", "none"]
EMERGENCY_NUMBERS = {"general": "112", "ambulance": ["108", "102"]}
MAPS_URL = "https://www.google.com/maps/search/maternity+hospital+near+me"


def questions_for(week: int | None) -> list[dict[str, Any]]:
    """The questions that apply at this week, most serious first."""
    out = []
    for q in rules()["screening"]["questions"]:
        if week is not None and ((q.get("min_week") and week < q["min_week"]) or (q.get("max_week") and week > q["max_week"])):
            continue
        out.append({k: q[k] for k in ("id", "level", "text", "source", "url")})
    out.sort(key=lambda q: ORDER.index(q["level"]))
    return out


def assess(answers: dict[str, bool], week: int | None, contact: dict[str, str] | None = None) -> dict[str, Any]:
    """Triage from yes/no answers. Unknown question ids are ignored; nothing is inferred from an unanswered question."""
    asked = {q["id"]: q for q in questions_for(week)}
    flagged = [asked[qid] for qid, yes in answers.items() if yes and qid in asked]
    level = "none"
    for candidate in ORDER[:-1]:
        if any(q["level"] == candidate for q in flagged):
            level = candidate
            break
    info = rules()["screening"]["levels"][level]
    return {
        "level": level,
        "title": info["title"],
        "action": info["action"],
        "flagged": [{"id": q["id"], "text": q["text"], "level": q["level"], "source": q["source"], "url": q["url"]} for q in flagged],
        "answered": len(answers),
        "emergency_numbers": EMERGENCY_NUMBERS,
        "maps_url": MAPS_URL,
        "contact": contact,
        "disclaimer": "This is a safety checklist, not a diagnosis. If you are worried, call your doctor or 112 regardless of the result.",
        "review": rules()["screening"].get("review", "pending_clinical_review"),
    }


def record(db: Session, user: User, result: dict[str, Any], week: int | None) -> ScreeningRecord:
    row = ScreeningRecord(user_id=user.id, week=week, level=result["level"], flagged=[f["id"] for f in result["flagged"]])
    db.add(row)
    db.flush()
    return row


def red_flag_level(flag_ids: list[str], week: int | None) -> str:
    return assess({qid: True for qid in flag_ids}, week)["level"]
