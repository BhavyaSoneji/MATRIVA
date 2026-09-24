from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models import (
    ConsentRecord,
    Conversation,
    Feedback,
    Message,
    PregnancyProfile,
    Recommendation,
)
from app.schemas.api import ConsentRequest, DeleteResponse
from app.services.audit import record_audit
from app.services.profile import profile_payload, pregnancy_payload, set_consent

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.post("/consent", response_model=DeleteResponse)
def update_consent(payload: ConsentRequest, user: CurrentUser, db: DBSession) -> DeleteResponse:
    set_consent(db, user, granted=payload.granted, version=payload.version)
    record_audit(
        db,
        actor_user_id=user.id,
        action="consent.grant" if payload.granted else "consent.revoke",
        resource_type="user",
        resource_id=user.id,
        details={"version": payload.version},
    )
    db.commit()
    return DeleteResponse(message="Consent updated" if payload.granted else "Consent withdrawn and profile data deleted")


@router.get("/export")
def export_data(user: CurrentUser, db: DBSession) -> dict[str, object]:
    conversations = db.execute(select(Conversation).where(Conversation.user_id == user.id)).scalars().all()
    conversation_ids = [item.id for item in conversations]
    messages: list[Message] = []
    if conversation_ids:
        messages = list(
            db.execute(select(Message).where(Message.conversation_id.in_(conversation_ids)).order_by(Message.created_at)).scalars().all()
        )
    pregnancy = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none()
    recommendations = db.execute(select(Recommendation).where(Recommendation.user_id == user.id)).scalars().all()
    feedback = db.execute(select(Feedback).where(Feedback.user_id == user.id)).scalars().all()
    consents = db.execute(select(ConsentRecord).where(ConsentRecord.user_id == user.id)).scalars().all()
    record_audit(db, actor_user_id=user.id, action="privacy.export", resource_type="user", resource_id=user.id)
    db.commit()
    return {
        "export_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "profile": profile_payload(db, user),
        "pregnancy": pregnancy_payload(pregnancy) if pregnancy else None,
        "conversations": [
            {
                "id": item.id,
                "title": item.title,
                "created_at": item.created_at.isoformat(),
                "messages": [
                    {
                        "id": message.id,
                        "role": message.role,
                        "content": message.content,
                        "intent": message.intent,
                        "safety_status": message.safety_status,
                        "created_at": message.created_at.isoformat(),
                    }
                    for message in messages
                    if message.conversation_id == item.id
                ],
            }
            for item in conversations
        ],
        "recommendations": [
            {
                "id": item.id,
                "domain": item.domain,
                "title": item.title,
                "description": item.description,
                "reason": item.reason,
                "evidence_level": item.evidence_level,
                "is_saved": item.is_saved,
                "created_at": item.created_at.isoformat(),
            }
            for item in recommendations
        ],
        "feedback": [
            {
                "id": item.id,
                "message_id": item.message_id,
                "recommendation_id": item.recommendation_id,
                "rating": item.rating,
                "comment": item.comment,
                "created_at": item.created_at.isoformat(),
            }
            for item in feedback
        ],
        "consents": [
            {
                "consent_type": item.consent_type,
                "granted": item.granted,
                "version": item.version,
                "granted_at": item.granted_at.isoformat() if item.granted_at else None,
                "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
            }
            for item in consents
        ],
    }


@router.delete("/account", response_model=DeleteResponse)
def delete_account(user: CurrentUser, db: DBSession) -> DeleteResponse:
    target_id = user.id
    record_audit(db, actor_user_id=target_id, action="privacy.account_delete", resource_type="user", resource_id=target_id)
    db.delete(user)
    db.commit()
    return DeleteResponse(message="Account and associated personal data deleted")
