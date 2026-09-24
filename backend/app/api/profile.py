from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models import ConsentRecord, CulturalProfile, DietaryProfile, HealthProfile, LifestyleProfile, PregnancyProfile
from app.schemas.api import DeleteResponse, PregnancyResponse, PregnancyUpdateRequest, ProfileResponse, ProfileUpdateRequest
from app.services.audit import record_audit
from app.services.profile import ConsentRequired, pregnancy_payload, profile_payload, update_pregnancy, update_profile

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
def get_profile(user: CurrentUser, db: DBSession) -> ProfileResponse:
    return ProfileResponse.model_validate(profile_payload(db, user))


@router.put("/profile", response_model=ProfileResponse)
def put_profile(payload: ProfileUpdateRequest, user: CurrentUser, db: DBSession) -> ProfileResponse:
    try:
        result = update_profile(db, user, payload)
    except ConsentRequired as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    db.commit()
    return ProfileResponse.model_validate(result)


@router.delete("/profile", response_model=DeleteResponse)
def delete_profile(user: CurrentUser, db: DBSession) -> DeleteResponse:
    for model in (HealthProfile, LifestyleProfile, DietaryProfile, CulturalProfile, PregnancyProfile):
        row = db.execute(select(model).where(model.user_id == user.id)).scalar_one_or_none()
        if row:
            db.delete(row)
    for consent in db.query(ConsentRecord).filter(ConsentRecord.user_id == user.id).all():
        db.delete(consent)
    user.consent_version = None
    record_audit(db, actor_user_id=user.id, action="profile.delete", resource_type="user", resource_id=user.id)
    db.commit()
    return DeleteResponse(message="Profile and health data deleted")


@router.get("/pregnancy", response_model=PregnancyResponse)
def get_pregnancy(user: CurrentUser, db: DBSession) -> PregnancyResponse:
    profile = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pregnancy profile not found")
    return PregnancyResponse.model_validate(pregnancy_payload(profile))


@router.put("/pregnancy", response_model=PregnancyResponse)
def put_pregnancy(payload: PregnancyUpdateRequest, user: CurrentUser, db: DBSession) -> PregnancyResponse:
    try:
        profile = update_pregnancy(db, user, payload)
    except ConsentRequired as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    db.commit()
    return PregnancyResponse.model_validate(pregnancy_payload(profile))


@router.delete("/pregnancy", response_model=DeleteResponse)
def delete_pregnancy(user: CurrentUser, db: DBSession) -> DeleteResponse:
    profile = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none()
    if profile:
        db.delete(profile)
        record_audit(db, actor_user_id=user.id, action="pregnancy.delete", resource_type="user", resource_id=user.id)
        db.commit()
    return DeleteResponse(message="Pregnancy profile deleted")
