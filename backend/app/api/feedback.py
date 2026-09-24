from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DBSession
from app.models import Feedback, Message, Recommendation
from app.schemas.api import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_feedback(payload: FeedbackRequest, user: CurrentUser, db: DBSession) -> FeedbackResponse:
    if payload.message_id:
        message = db.get(Message, payload.message_id)
        if message is None or message.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if payload.recommendation_id:
        recommendation = db.get(Recommendation, payload.recommendation_id)
        if recommendation is None or recommendation.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    item = Feedback(
        user_id=user.id,
        message_id=payload.message_id,
        recommendation_id=payload.recommendation_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(item)
    db.commit()
    return FeedbackResponse.model_validate(item)


@router.get("/admin", response_model=list[FeedbackResponse])
def list_feedback(admin: AdminUser, db: DBSession) -> list[FeedbackResponse]:
    items = db.execute(select(Feedback).order_by(Feedback.created_at.desc()).limit(500)).scalars().all()
    return [FeedbackResponse.model_validate(item) for item in items]
