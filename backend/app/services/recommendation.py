from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DietaryProfile,
    ExerciseGuidance,
    FoodItem,
    PregnancyProfile,
    Recommendation,
    SafetyStatus,
    User,
)
from app.rag.retrieval import retrieve_chunks
from app.schemas.api import RecommendationResponse
from app.services.stage import calculate_stage


def _profile_preferences(db: Session, user: User) -> tuple[str | None, str | None, str | None]:
    pregnancy = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none()
    dietary = db.execute(select(DietaryProfile).where(DietaryProfile.user_id == user.id)).scalar_one_or_none()
    stage = calculate_stage(pregnancy.current_week).stage if pregnancy else None
    return stage, dietary.region if dietary else None, dietary.diet_type if dietary else None


def generate_recommendations(
    db: Session,
    user: User,
    *,
    intent: str | None = None,
    limit: int = 5,
) -> list[Recommendation]:
    stage, region, diet = _profile_preferences(db, user)
    if not stage:
        return []
    intent_queries = {
        "NUTRITION": "nutrition food meal",
        "FOOD": "nutrition food meal",
        "EXERCISE": "exercise activity walking",
        "LIFESTYLE": "lifestyle activity sleep routine",
        "ANTENATAL_CARE": "antenatal check-up visit",
        "AYURVEDA": "ayurveda traditional garbhini",
    }
    query = intent_queries.get((intent or "").upper(), intent or "pregnancy guidance")
    chunks = retrieve_chunks(db, query, stage=stage, region=region, limit=max(limit, 8))
    recommendations: list[Recommendation] = []
    seen_titles: set[str] = set()
    for item in chunks:
        title = " ".join(item.chunk.content.split())[:120]
        if title in seen_titles:
            continue
        seen_titles.add(title)
        source = item.source
        if source.review_status != "approved":
            continue
        source_safety = str((source.extra_metadata or {}).get("safety_status", SafetyStatus.SAFE_GENERAL.value))
        if source_safety in {SafetyStatus.HIGH_RISK.value, SafetyStatus.URGENT_ESCALATION.value}:
            continue
        recommendations.append(
            Recommendation(
                user_id=user.id,
                domain=item.document.domain,
                title=item.document.title,
                description=item.chunk.content[:1500],
                reason=(
                    f"Shown because you are in {stage.replace('_', ' ')}"
                    + (f", your region is {region}" if region else "")
                    + f", and this reviewed {item.document.domain} source matched your question."
                ),
                source_documents=[item.document.id],
                evidence_level=source.evidence_level,
                safety_status=SafetyStatus.SAFE_GENERAL.value,
                score=item.score,
            )
        )
        if len(recommendations) >= limit:
            break

    # Structured food records are only recommended when their evidence is separate from
    # cultural/traditional status and a reviewed source exists.
    if not recommendations and (intent or "").upper() in {"NUTRITION", "FOOD", ""}:
        foods = db.execute(select(FoodItem).where(FoodItem.active.is_(True))).scalars().all()
        for food_item in foods:
            if region and food_item.region and food_item.region != region:
                continue
            if diet and diet.lower() not in {str(value).lower() for value in (food_item.dietary_types or [])}:
                continue
            if not food_item.source_ids:
                continue
            recommendations.append(
                Recommendation(
                    user_id=user.id,
                    domain="nutrition",
                    title=food_item.name,
                    description=food_item.pregnancy_context or "Review the source and suitability with your maternity-care professional.",
                    reason=(
                        f"Shown because it matches your {diet or 'diet'} profile"
                        + (f" and region {region}" if region else "")
                        + "; cultural relevance is not treated as proof of safety."
                    ),
                    source_documents=food_item.source_ids,
                    evidence_level=food_item.evidence_status,
                    safety_status=food_item.safety_status,
                    score=1.0,
                )
            )
            if len(recommendations) >= limit:
                break

    # Structured lifestyle records are only recommended when they have a source.
    if not recommendations and intent in {None, "", "lifestyle", "exercise", "nutrition", "food"}:
        lifestyle = db.execute(
            select(ExerciseGuidance).where(
                ExerciseGuidance.active.is_(True),
                ExerciseGuidance.safety_status.notin_([SafetyStatus.HIGH_RISK.value, SafetyStatus.URGENT_ESCALATION.value]),
            )
        ).scalars().all()
        for lifestyle_item in lifestyle:
            if lifestyle_item.suitable_stages and stage not in lifestyle_item.suitable_stages:
                continue
            if not lifestyle_item.source_ids:
                continue
            recommendations.append(
                Recommendation(
                    user_id=user.id,
                    domain="lifestyle",
                    title=lifestyle_item.title,
                    description=lifestyle_item.description,
                    reason=f"Shown because it is applicable to your {stage.replace('_', ' ')} profile and passed the configured safety filter.",
                    source_documents=lifestyle_item.source_ids,
                    evidence_level=lifestyle_item.evidence_status,
                    safety_status=lifestyle_item.safety_status,
                    score=1.0,
                )
            )
            if len(recommendations) >= limit:
                break
    for recommendation in recommendations:
        db.add(recommendation)
    db.flush()
    return recommendations


def recommendation_payload(item: Recommendation) -> RecommendationResponse:
    return RecommendationResponse.model_validate(item)
