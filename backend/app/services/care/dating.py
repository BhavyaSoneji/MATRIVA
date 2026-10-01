"""Gestational age from a date, not from a number that goes stale.

A woman who typed "week 12" in March is not at week 12 in June. The app stores the last menstrual period (LMP) or the
expected due date (EDD) and works the week out from today, so the plan, reminders and visit calendar stay correct
without her doing anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PregnancyDating, PregnancyProfile, User
from app.services.profile import ConsentRequired, has_consent
from app.services.stage import calculate_stage

GESTATION_DAYS = 280  # 40 weeks from LMP (Naegele's rule)
MAX_WEEK = 42


class DatingError(ValueError):
    pass


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


@dataclass(frozen=True)
class Dating:
    lmp: date
    edd: date
    source: str  # lmp | edd | week
    week: int  # completed weeks + 1, clamped to 1..42 (the "week you are in")
    day: int  # 1..7 within that week
    trimester: int
    stage: str
    days_to_edd: int
    pre_pregnancy_weight_kg: float | None

    @property
    def progress(self) -> float:
        return min(1.0, max(0.0, (GESTATION_DAYS - self.days_to_edd) / GESTATION_DAYS))


def week_from_lmp(lmp: date, today: date) -> tuple[int, int]:
    days = (today - lmp).days
    return min(max(days // 7 + 1, 1), MAX_WEEK), days % 7 + 1


def build(lmp: date, source: str, today: date, pre_weight: float | None = None) -> Dating:
    week, day = week_from_lmp(lmp, today)
    stage = calculate_stage(week)
    edd = lmp + timedelta(days=GESTATION_DAYS)
    return Dating(lmp, edd, source, week, day, stage.trimester, stage.stage, (edd - today).days, pre_weight)


def validate_lmp(lmp: date, today: date) -> None:
    if lmp > today:
        raise DatingError("The last period date cannot be in the future.")
    if (today - lmp).days > 300:
        raise DatingError("That date is more than 42 weeks ago. Please check it, or enter your due date instead.")


def resolve(db: Session, user: User, today: date | None = None) -> Dating | None:
    """The current dating for a user, from the stored dates, or estimated from a plain week number, or None."""
    today = today or today_utc()
    row = db.execute(select(PregnancyDating).where(PregnancyDating.user_id == user.id)).scalar_one_or_none()
    if row is not None:
        lmp = row.lmp_date or (row.edd_date - timedelta(days=GESTATION_DAYS) if row.edd_date else None)
        if lmp is not None:  # a row with neither date cannot be dated; fall back to the plain week below
            return build(lmp, row.source, today, row.pre_pregnancy_weight_kg)
    profile = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none()
    if profile is None:
        return None
    # only a week number is known: assume it was true when it was last saved and move forward from there
    saved = (profile.updated_at or profile.created_at or datetime.now(timezone.utc)).date()
    lmp = saved - timedelta(days=(profile.current_week - 1) * 7)
    return build(lmp, "week", today)


def save(
    db: Session,
    user: User,
    *,
    lmp: date | None = None,
    edd: date | None = None,
    week: int | None = None,
    pre_pregnancy_weight_kg: float | None = None,
    first_pregnancy: bool | None = None,
    today: date | None = None,
) -> Dating:
    if not has_consent(db, user.id):
        raise ConsentRequired("Explicit consent is required before pregnancy data can be stored")
    today = today or today_utc()
    given = [x for x in (lmp, edd, week) if x is not None]
    if len(given) != 1:
        raise DatingError("Give exactly one of: last period date, due date, or current week.")
    if lmp is not None:
        source = "lmp"
        validate_lmp(lmp, today)
    elif edd is not None:
        source = "edd"
        lmp = edd - timedelta(days=GESTATION_DAYS)
        validate_lmp(lmp, today)
    else:
        source = "week"
        if week is None or not 1 <= week <= MAX_WEEK:
            raise DatingError("The week must be between 1 and 42.")
        lmp = today - timedelta(days=(week - 1) * 7)
    if pre_pregnancy_weight_kg is not None and not 25 <= pre_pregnancy_weight_kg <= 200:
        raise DatingError("Please check the weight (25-200 kg).")

    row = db.execute(select(PregnancyDating).where(PregnancyDating.user_id == user.id)).scalar_one_or_none() or PregnancyDating(user_id=user.id)
    row.lmp_date = lmp
    row.edd_date = lmp + timedelta(days=GESTATION_DAYS)
    row.source = source
    if pre_pregnancy_weight_kg is not None:
        row.pre_pregnancy_weight_kg = pre_pregnancy_weight_kg
    db.add(row)

    dating = build(lmp, source, today, row.pre_pregnancy_weight_kg)
    profile = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none() or PregnancyProfile(
        user_id=user.id, first_pregnancy=True
    )
    sync_profile(profile, dating)
    if first_pregnancy is not None:
        profile.first_pregnancy = first_pregnancy
    db.add(profile)
    db.flush()
    return dating


def sync_profile(profile: PregnancyProfile, dating: Dating) -> None:
    """Keep the older PregnancyProfile row (used by chat, recommendations and retrieval) in step with the dates."""
    profile.current_week = dating.week
    profile.due_date = dating.edd
    profile.stage = dating.stage


def refresh_profile(db: Session, user: User) -> None:
    """Called whenever the pregnancy is read: roll the stored week forward to today."""
    row = db.execute(select(PregnancyDating).where(PregnancyDating.user_id == user.id)).scalar_one_or_none()
    profile = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none()
    if row is None or profile is None:
        return
    dating = resolve(db, user)
    if dating and (profile.current_week, profile.stage) != (dating.week, dating.stage):
        sync_profile(profile, dating)
        db.flush()
