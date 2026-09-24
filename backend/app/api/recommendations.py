from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models import Recommendation
from app.schemas.api import RecommendationRequest, RecommendationResponse
from app.services.recommendation import generate_recommendations, recommendation_payload

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/generate", response_model=list[RecommendationResponse])
def create_recommendations(payload: RecommendationRequest, user: CurrentUser, db: DBSession) -> list[RecommendationResponse]:
    items = generate_recommendations(db, user, intent=payload.intent, limit=payload.limit)
    db.commit()
    return [recommendation_payload(item) for item in items]


@router.get("", response_model=list[RecommendationResponse])
def list_recommendations(
    user: CurrentUser,
    db: DBSession,
    saved_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RecommendationResponse]:
    statement = select(Recommendation).where(Recommendation.user_id == user.id)
    if saved_only:
        statement = statement.where(Recommendation.is_saved.is_(True))
    statement = statement.order_by(Recommendation.created_at.desc()).limit(limit)
    return [recommendation_payload(item) for item in db.execute(statement).scalars().all()]


@router.post("/{recommendation_id}/save", response_model=RecommendationResponse)
def save_recommendation(recommendation_id: str, user: CurrentUser, db: DBSession) -> RecommendationResponse:
    item = db.get(Recommendation, recommendation_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    item.is_saved = True
    db.commit()
    return recommendation_payload(item)


@router.delete("/{recommendation_id}/save", response_model=RecommendationResponse)
def unsave_recommendation(recommendation_id: str, user: CurrentUser, db: DBSession) -> RecommendationResponse:
    item = db.get(Recommendation, recommendation_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    item.is_saved = False
    db.commit()
    return recommendation_payload(item)
