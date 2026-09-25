from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyWellnessLog, User
from app.schemas.api import WellnessLogRequest

MAX_SUMMARY_DAYS = 30


def _log_for_date(db: Session, user_id: str, log_date: date) -> DailyWellnessLog | None:
    return db.execute(
        select(DailyWellnessLog).where(
            DailyWellnessLog.user_id == user_id,
            DailyWellnessLog.log_date == log_date,
        )
    ).scalar_one_or_none()


def upsert_daily_log(db: Session, user: User, payload: WellnessLogRequest) -> DailyWellnessLog:
    target_date = payload.date or datetime.now(timezone.utc).date()
    log = _log_for_date(db, user.id, target_date) or DailyWellnessLog(user_id=user.id, log_date=target_date)

    if payload.water_intake_ml is not None:
        log.water_intake_ml = payload.water_intake_ml
    if payload.sleep_hours is not None:
        log.sleep_hours = payload.sleep_hours
    if payload.activity_minutes is not None:
        log.activity_minutes = payload.activity_minutes

    db.add(log)
    db.flush()
    return log


def get_daily_log(db: Session, user: User, target_date: date) -> DailyWellnessLog | None:
    return _log_for_date(db, user.id, target_date)


def get_summary(db: Session, user: User, days: int) -> list[DailyWellnessLog]:
    days = max(1, min(days, MAX_SUMMARY_DAYS))
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    rows = db.execute(
        select(DailyWellnessLog)
        .where(
            DailyWellnessLog.user_id == user.id,
            DailyWellnessLog.log_date >= start_date,
        )
        .order_by(DailyWellnessLog.log_date.asc())
    ).scalars().all()
    return list(rows)
