"""Build the personalised USER CONTEXT that is passed to retrieval and to the model.

Health details (conditions, allergies, restrictions) are only included when the user has
given explicit consent -- the same gate that protects storing them in the first place.
Names and contact details are never included.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CulturalProfile, DietaryProfile, HealthProfile, PregnancyProfile, User
from app.rag.reranking import UserContext
from app.services.profile import has_consent
from app.services.stage import calculate_stage

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "gu": "Gujarati"}


def _one(db: Session, model, user_id: str):
    return db.execute(select(model).where(model.user_id == user_id)).scalar_one_or_none()


def build_user_context(db: Session, user: User | None, language: str | None = None) -> UserContext:
    reply_language = LANGUAGE_NAMES.get(language or "")
    if user is None:
        return UserContext(reply_language=reply_language)

    pregnancy = _one(db, PregnancyProfile, user.id)
    dietary = _one(db, DietaryProfile, user.id)
    stage = calculate_stage(pregnancy.current_week).stage if pregnancy else None

    notes: list[str] = []
    terms: list[str] = []
    if pregnancy:
        notes.append(f"week {pregnancy.current_week} of pregnancy ({stage.replace('_', ' ')})")
        notes.append("first pregnancy" if pregnancy.first_pregnancy else "has been pregnant before")
    if dietary:
        if dietary.diet_type:
            notes.append(f"diet: {dietary.diet_type}")
            terms.append(dietary.diet_type)
        if dietary.cuisine:
            notes.append(f"cuisine: {dietary.cuisine}")

    if has_consent(db, user.id):
        health = _one(db, HealthProfile, user.id)
        cultural = _one(db, CulturalProfile, user.id)
        if health:
            allergies = sorted({*(health.allergies or []), *(dietary.allergies if dietary else [])})
            if allergies:
                notes.append("allergies: " + ", ".join(allergies))
            if health.known_conditions:
                notes.append("known conditions: " + ", ".join(health.known_conditions))
            restrictions = [*(health.doctor_restrictions or []), *(health.dietary_restrictions or []), *(health.activity_restrictions or [])]
            if restrictions:
                notes.append("restrictions from their doctor/diet: " + ", ".join(restrictions))
        if cultural and cultural.traditional_practice_preference:
            notes.append(f"traditional-practice preference: {cultural.traditional_practice_preference}")
        if reply_language is None and cultural and cultural.language:
            reply_language = LANGUAGE_NAMES.get(cultural.language.lower()[:2]) or None

    return UserContext(
        pregnancy_stage=stage,
        region=dietary.region if dietary else None,
        context_terms=terms,
        profile_notes=notes,
        reply_language=reply_language,
    )
