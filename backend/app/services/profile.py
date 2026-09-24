from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ConsentRecord,
    CulturalProfile,
    DietaryProfile,
    HealthProfile,
    LifestyleProfile,
    PregnancyProfile,
    User,
)
from app.schemas.api import PregnancyUpdateRequest, ProfileUpdateRequest
from app.services.stage import calculate_stage


class ConsentRequired(PermissionError):
    pass


def _consent(db: Session, user_id: str) -> ConsentRecord | None:
    return db.execute(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user_id, ConsentRecord.granted.is_(True), ConsentRecord.revoked_at.is_(None))
        .order_by(ConsentRecord.granted_at.desc())
    ).scalars().first()


def has_consent(db: Session, user_id: str) -> bool:
    return _consent(db, user_id) is not None


def _profile_for_user(db: Session, model: Any, user_id: str) -> Any:
    return db.execute(select(model).where(model.user_id == user_id)).scalar_one_or_none()


def update_profile(db: Session, user: User, payload: ProfileUpdateRequest) -> dict[str, object]:
    if not payload.consent:
        raise ConsentRequired("Explicit consent is required before health/profile data can be stored")

    user.full_name = payload.full_name.strip() if payload.full_name else None
    user.consent_version = payload.consent_version
    now = datetime.now(timezone.utc)
    old_consent = _consent(db, user.id)
    if old_consent is None or old_consent.version != payload.consent_version:
        if old_consent:
            old_consent.revoked_at = now
        db.add(
            ConsentRecord(
                user_id=user.id,
                consent_type="profile_and_health",
                granted=True,
                version=payload.consent_version,
                granted_at=now,
            )
        )

    health = _profile_for_user(db, HealthProfile, user.id) or HealthProfile(user_id=user.id)
    health.known_conditions = payload.known_conditions
    health.doctor_restrictions = payload.doctor_restrictions
    health.dietary_restrictions = payload.dietary_restrictions
    health.activity_restrictions = payload.activity_restrictions
    health.allergies = payload.allergies
    health.notes = payload.health_notes
    db.add(health)

    lifestyle = _profile_for_user(db, LifestyleProfile, user.id) or LifestyleProfile(user_id=user.id)
    lifestyle.activity_level = payload.activity_level
    lifestyle.occupation = payload.occupation
    lifestyle.sleep_hours = payload.sleep_hours
    lifestyle.stress_level = payload.stress_level
    lifestyle.preferences = payload.lifestyle_preferences
    db.add(lifestyle)

    dietary = _profile_for_user(db, DietaryProfile, user.id) or DietaryProfile(user_id=user.id)
    dietary.diet_type = payload.diet_type
    dietary.region = payload.region
    dietary.cuisine = payload.cuisine
    dietary.food_preferences = payload.food_preferences
    dietary.allergies = payload.allergies
    db.add(dietary)

    cultural = _profile_for_user(db, CulturalProfile, user.id) or CulturalProfile(user_id=user.id)
    cultural.language = payload.language
    cultural.region = payload.region
    cultural.traditional_practice_preference = payload.traditional_practice_preference
    cultural.cultural_notes = payload.cultural_notes
    db.add(cultural)
    db.flush()
    return profile_payload(db, user)


def profile_payload(db: Session, user: User) -> dict[str, object]:
    health = _profile_for_user(db, HealthProfile, user.id)
    lifestyle = _profile_for_user(db, LifestyleProfile, user.id)
    dietary = _profile_for_user(db, DietaryProfile, user.id)
    cultural = _profile_for_user(db, CulturalProfile, user.id)
    consent = _consent(db, user.id)
    return {
        "user_id": user.id,
        "consent": consent is not None,
        "consent_version": consent.version if consent else user.consent_version,
        "full_name": user.full_name,
        "health": {
            "known_conditions": health.known_conditions,
            "doctor_restrictions": health.doctor_restrictions,
            "dietary_restrictions": health.dietary_restrictions,
            "activity_restrictions": health.activity_restrictions,
            "allergies": health.allergies,
            "notes": health.notes,
        } if health else None,
        "lifestyle": {
            "activity_level": lifestyle.activity_level,
            "occupation": lifestyle.occupation,
            "sleep_hours": lifestyle.sleep_hours,
            "stress_level": lifestyle.stress_level,
            "preferences": lifestyle.preferences,
        } if lifestyle else None,
        "dietary": {
            "diet_type": dietary.diet_type,
            "region": dietary.region,
            "cuisine": dietary.cuisine,
            "food_preferences": dietary.food_preferences,
            "allergies": dietary.allergies,
        } if dietary else None,
        "cultural": {
            "language": cultural.language,
            "region": cultural.region,
            "traditional_practice_preference": cultural.traditional_practice_preference,
            "cultural_notes": cultural.cultural_notes,
        } if cultural else None,
    }


def set_consent(db: Session, user: User, *, granted: bool, version: str) -> None:
    now = datetime.now(timezone.utc)
    current = _consent(db, user.id)
    if granted:
        if current is None:
            db.add(
                ConsentRecord(
                    user_id=user.id,
                    consent_type="profile_and_health",
                    granted=True,
                    version=version,
                    granted_at=now,
                )
            )
        else:
            current.version = version
            current.revoked_at = None
        user.consent_version = version
        return

    if current:
        current.granted = False
        current.revoked_at = now
    user.consent_version = None
    for model in (HealthProfile, LifestyleProfile, DietaryProfile, CulturalProfile, PregnancyProfile):
        row = _profile_for_user(db, model, user.id)
        if row:
            db.delete(row)
    db.flush()


def update_pregnancy(db: Session, user: User, payload: PregnancyUpdateRequest) -> PregnancyProfile:
    if not has_consent(db, user.id):
        raise ConsentRequired("Explicit consent is required before pregnancy data can be stored")
    stage = calculate_stage(payload.current_week)
    profile = _profile_for_user(db, PregnancyProfile, user.id) or PregnancyProfile(user_id=user.id)
    profile.current_week = payload.current_week
    profile.due_date = payload.due_date
    profile.first_pregnancy = payload.first_pregnancy
    profile.stage = stage.stage
    db.add(profile)
    db.flush()
    return profile


def pregnancy_payload(profile: PregnancyProfile) -> dict[str, object]:
    stage = calculate_stage(profile.current_week)
    return {
        "current_week": profile.current_week,
        "due_date": profile.due_date,
        "first_pregnancy": profile.first_pregnancy,
        "stage": stage.stage,
        "trimester": stage.trimester,
    }
