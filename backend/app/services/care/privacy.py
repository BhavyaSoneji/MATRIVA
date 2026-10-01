"""Remove every care record for a user (consent withdrawn, profile deleted)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import (
    DailyCheckin,
    DailyWellnessLog,
    EmergencyContact,
    HealthReading,
    MealLog,
    PregnancyDating,
    ScreeningRecord,
)

CARE_MODELS = (PregnancyDating, EmergencyContact, DailyCheckin, HealthReading, MealLog, ScreeningRecord, DailyWellnessLog)


def purge(db: Session, user_id: str) -> int:
    n = 0
    for model in CARE_MODELS:
        n += db.execute(delete(model).where(model.user_id == user_id)).rowcount or 0
    db.flush()
    return n


def export(db: Session, user_id: str) -> dict[str, list[dict]]:
    """Everything stored, for the privacy export."""
    from sqlalchemy import select

    out: dict[str, list[dict]] = {}
    for model in CARE_MODELS:
        rows = db.execute(select(model).where(model.user_id == user_id)).scalars().all()
        out[model.__tablename__] = [
            {c.name: (v.isoformat() if hasattr(v, "isoformat") else v) for c in model.__table__.columns if (v := getattr(r, c.name)) is not None}
            for r in rows
        ]
    return out
