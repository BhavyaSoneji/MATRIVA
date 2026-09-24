from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import AdminUser, DBSession
from app.core.config import get_settings
from app.core.security import sanitize_filename
from app.models import (
    AuditLog,
    AyurvedicSource,
    EvidenceMetadata,
    ExerciseGuidance,
    FoodItem,
    Guideline,
    IndexStatus,
    KnowledgeDocument,
    KnowledgeSource,
    ReviewStatus,
    SafetyEvent,
    SafetyRule,
)
from app.repositories.knowledge import source_payload
from app.schemas.api import (
    AyurvedaSourceRequest,
    DocumentMetadataRequest,
    DocumentResponse,
    ExerciseGuidanceRequest,
    FoodItemRequest,
    GuidelineRequest,
    GuidelineResponse,
    SafetyEventResponse,
    SafetyRuleRequest,
    SafetyRuleResponse,
    SourceResponse,
)
from app.services.audit import record_audit
from app.services.knowledge import DocumentProcessingError, create_document, reindex_document

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/json",
    "text/csv",
}
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".json", ".csv"}


def _guideline_status(item: Guideline) -> str:
    if item.review_due_date is not None and item.review_due_date < date.today():
        return "stale"
    return item.status


def _document_response(document: KnowledgeDocument) -> DocumentResponse:
    return DocumentResponse.model_validate({
        "id": document.id,
        "source_id": document.source_id,
        "title": document.title,
        "domain": document.domain,
        "subdomain": document.subdomain,
        "language": document.language,
        "region": document.region,
        "pregnancy_stage": document.pregnancy_stage,
        "review_status": document.review_status,
        "index_status": document.index_status,
        "content_hash": document.content_hash,
        "file_name": document.file_name,
        "mime_type": document.mime_type,
        "active": document.active,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "source": source_payload(document.source),
    })


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(admin: AdminUser, db: DBSession) -> list[DocumentResponse]:
    documents = db.execute(select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).limit(500)).scalars().all()
    return [_document_response(item) for item in documents]


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    admin: AdminUser,
    db: DBSession,
    metadata: str = Form(...),
    file: UploadFile = File(...),
) -> DocumentResponse:
    try:
        parsed = DocumentMetadataRequest.model_validate(json.loads(metadata))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="metadata must be valid JSON") from exc

    filename = sanitize_filename(file.filename)
    extension = Path(filename).suffix.lower()
    if file.content_type not in ALLOWED_MIME_TYPES or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported document type")
    raw = await file.read(get_settings().max_upload_bytes + 1)
    if len(raw) > get_settings().max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Document is too large")
    try:
        document = create_document(db, raw_content=raw, metadata=parsed, created_by=admin.id, original_filename=file.filename)
        document.mime_type = file.content_type or "application/octet-stream"
        db.commit()
    except DocumentProcessingError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _document_response(document)


@router.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document(document_id: str, payload: DocumentMetadataRequest, admin: AdminUser, db: DBSession) -> DocumentResponse:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    for field in ("title", "domain", "subdomain", "language", "region", "pregnancy_stage"):
        setattr(document, field, getattr(payload, field))
    document.updated_at = datetime.now(timezone.utc)
    record_audit(db, actor_user_id=admin.id, action="document.update", resource_type="knowledge_document", resource_id=document.id)
    db.commit()
    return _document_response(document)


@router.post("/documents/{document_id}/approve", response_model=DocumentResponse)
def approve_document(document_id: str, admin: AdminUser, db: DBSession) -> DocumentResponse:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.index_status != IndexStatus.INDEXED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document must be successfully indexed before approval")
    now = datetime.now(timezone.utc)
    document.review_status = ReviewStatus.APPROVED.value
    document.active = True
    document.approved_by = admin.id
    document.approved_at = now
    source = document.source
    source.review_status = ReviewStatus.APPROVED.value
    if source.evidence_metadata is None:
        source.evidence_metadata = EvidenceMetadata(
            source_id=source.id,
            evidence_level=source.evidence_level,
            review_status=ReviewStatus.APPROVED.value,
            reviewer=admin.email,
            reviewed_at=now,
        )
    else:
        source.evidence_metadata.review_status = ReviewStatus.APPROVED.value
        source.evidence_metadata.reviewer = admin.email
        source.evidence_metadata.reviewed_at = now
    record_audit(db, actor_user_id=admin.id, action="document.approve", resource_type="knowledge_document", resource_id=document.id)
    db.commit()
    return _document_response(document)


@router.post("/documents/{document_id}/reject", response_model=DocumentResponse)
def reject_document(document_id: str, admin: AdminUser, db: DBSession) -> DocumentResponse:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document.review_status = ReviewStatus.REJECTED.value
    document.active = False
    record_audit(db, actor_user_id=admin.id, action="document.reject", resource_type="knowledge_document", resource_id=document.id)
    db.commit()
    return _document_response(document)


@router.post("/documents/{document_id}/reindex", response_model=DocumentResponse)
def reindex(document_id: str, admin: AdminUser, db: DBSession) -> DocumentResponse:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document.review_status = ReviewStatus.PENDING.value
    document.active = False
    try:
        reindex_document(db, document)
    except DocumentProcessingError as exc:
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    record_audit(db, actor_user_id=admin.id, action="document.reindex", resource_type="knowledge_document", resource_id=document.id)
    db.commit()
    return _document_response(document)




def _validate_source_ids(db: DBSession, source_ids: list[str]) -> None:
    if not source_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one reviewed source is required")
    for source_id in source_ids:
        source = db.get(KnowledgeSource, source_id)
        if source is None or source.review_status != ReviewStatus.APPROVED.value:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="All content sources must be approved")


@router.get("/food-items")
def list_food_items(admin: AdminUser, db: DBSession) -> list[dict[str, object]]:
    items = db.execute(select(FoodItem).order_by(FoodItem.created_at.desc()).limit(500)).scalars().all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "local_names": item.local_names,
            "region": item.region,
            "cuisine": item.cuisine,
            "ingredients": item.ingredients,
            "dietary_types": item.dietary_types,
            "season": item.season,
            "nutrition_metadata": item.nutrition_metadata,
            "cultural_relevance": item.cultural_relevance,
            "pregnancy_context": item.pregnancy_context,
            "evidence_status": item.evidence_status,
            "safety_status": item.safety_status,
            "source_ids": item.source_ids,
            "active": item.active,
        }
        for item in items
    ]


@router.post("/food-items", status_code=status.HTTP_201_CREATED)
def create_food_item(payload: FoodItemRequest, admin: AdminUser, db: DBSession) -> dict[str, object]:
    _validate_source_ids(db, payload.source_ids)
    item = FoodItem(**payload.model_dump())
    db.add(item)
    db.flush()
    record_audit(db, actor_user_id=admin.id, action="food_item.create", resource_type="food_item", resource_id=item.id)
    db.commit()
    return {"id": item.id, "name": item.name}


@router.put("/food-items/{item_id}")
def update_food_item(item_id: str, payload: FoodItemRequest, admin: AdminUser, db: DBSession) -> dict[str, object]:
    item = db.get(FoodItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food item not found")
    _validate_source_ids(db, payload.source_ids)
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    record_audit(db, actor_user_id=admin.id, action="food_item.update", resource_type="food_item", resource_id=item.id)
    db.commit()
    return {"id": item.id, "name": item.name}


@router.delete("/food-items/{item_id}")
def delete_food_item(item_id: str, admin: AdminUser, db: DBSession) -> dict[str, str]:
    item = db.get(FoodItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food item not found")
    item.active = False
    record_audit(db, actor_user_id=admin.id, action="food_item.deactivate", resource_type="food_item", resource_id=item.id)
    db.commit()
    return {"message": "Food item deactivated"}


@router.get("/exercise-guidance")
def list_exercise_guidance(admin: AdminUser, db: DBSession) -> list[dict[str, object]]:
    items = db.execute(select(ExerciseGuidance).order_by(ExerciseGuidance.created_at.desc()).limit(500)).scalars().all()
    return [
        {
            "id": item.id,
            "category": item.category,
            "title": item.title,
            "description": item.description,
            "suitable_stages": item.suitable_stages,
            "restrictions": item.restrictions,
            "evidence_status": item.evidence_status,
            "safety_status": item.safety_status,
            "source_ids": item.source_ids,
            "active": item.active,
        }
        for item in items
    ]


@router.post("/exercise-guidance", status_code=status.HTTP_201_CREATED)
def create_exercise_guidance(payload: ExerciseGuidanceRequest, admin: AdminUser, db: DBSession) -> dict[str, object]:
    _validate_source_ids(db, payload.source_ids)
    item = ExerciseGuidance(**payload.model_dump())
    db.add(item)
    db.flush()
    record_audit(db, actor_user_id=admin.id, action="exercise_guidance.create", resource_type="exercise_guidance", resource_id=item.id)
    db.commit()
    return {"id": item.id, "title": item.title}


@router.put("/exercise-guidance/{item_id}")
def update_exercise_guidance(item_id: str, payload: ExerciseGuidanceRequest, admin: AdminUser, db: DBSession) -> dict[str, object]:
    item = db.get(ExerciseGuidance, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise guidance not found")
    _validate_source_ids(db, payload.source_ids)
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    record_audit(db, actor_user_id=admin.id, action="exercise_guidance.update", resource_type="exercise_guidance", resource_id=item.id)
    db.commit()
    return {"id": item.id, "title": item.title}


@router.delete("/exercise-guidance/{item_id}")
def delete_exercise_guidance(item_id: str, admin: AdminUser, db: DBSession) -> dict[str, str]:
    item = db.get(ExerciseGuidance, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise guidance not found")
    item.active = False
    record_audit(db, actor_user_id=admin.id, action="exercise_guidance.deactivate", resource_type="exercise_guidance", resource_id=item.id)
    db.commit()
    return {"message": "Exercise guidance deactivated"}


@router.get("/safety-rules", response_model=list[SafetyRuleResponse])
def list_safety_rules(admin: AdminUser, db: DBSession) -> list[SafetyRuleResponse]:
    return [SafetyRuleResponse.model_validate(item) for item in db.execute(select(SafetyRule).order_by(SafetyRule.created_at.desc())).scalars().all()]


@router.post("/safety-rules", response_model=SafetyRuleResponse, status_code=status.HTTP_201_CREATED)
def create_safety_rule(payload: SafetyRuleRequest, admin: AdminUser, db: DBSession) -> SafetyRuleResponse:
    item = SafetyRule(**payload.model_dump(exclude={"reviewed_by"}), reviewed_by=payload.reviewed_by or admin.email, reviewed_at=datetime.now(timezone.utc))
    db.add(item)
    db.flush()
    record_audit(db, actor_user_id=admin.id, action="safety_rule.create", resource_type="safety_rule", resource_id=item.id)
    db.commit()
    return SafetyRuleResponse.model_validate(item)


@router.put("/safety-rules/{rule_id}", response_model=SafetyRuleResponse)
def update_safety_rule(rule_id: str, payload: SafetyRuleRequest, admin: AdminUser, db: DBSession) -> SafetyRuleResponse:
    item = db.get(SafetyRule, rule_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety rule not found")
    for field, value in payload.model_dump(exclude={"reviewed_by"}).items():
        setattr(item, field, value)
    item.reviewed_by = payload.reviewed_by or admin.email
    item.reviewed_at = datetime.now(timezone.utc)
    record_audit(db, actor_user_id=admin.id, action="safety_rule.update", resource_type="safety_rule", resource_id=item.id)
    db.commit()
    return SafetyRuleResponse.model_validate(item)


@router.delete("/safety-rules/{rule_id}")
def delete_safety_rule(rule_id: str, admin: AdminUser, db: DBSession) -> dict[str, str]:
    item = db.get(SafetyRule, rule_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety rule not found")
    db.delete(item)
    record_audit(db, actor_user_id=admin.id, action="safety_rule.delete", resource_type="safety_rule", resource_id=rule_id)
    db.commit()
    return {"message": "Safety rule deleted"}


@router.get("/safety-events", response_model=list[SafetyEventResponse])
def list_safety_events(admin: AdminUser, db: DBSession) -> list[SafetyEventResponse]:
    items = db.execute(select(SafetyEvent).order_by(SafetyEvent.created_at.desc()).limit(500)).scalars().all()
    return [SafetyEventResponse.model_validate(item) for item in items]


@router.get("/audit-logs")
def list_audit_logs(admin: AdminUser, db: DBSession) -> list[dict[str, object]]:
    items = db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)).scalars().all()
    return [
        {
            "id": item.id,
            "actor_user_id": item.actor_user_id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "details": item.details,
            "created_at": item.created_at,
        }
        for item in items
    ]


@router.post("/ayurveda-sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_ayurveda_source(payload: AyurvedaSourceRequest, admin: AdminUser, db: DBSession) -> SourceResponse:
    source = db.get(KnowledgeSource, payload.source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")
    existing = db.execute(select(AyurvedicSource).where(AyurvedicSource.source_id == source.id)).scalar_one_or_none()
    values = payload.model_dump(exclude={"source_id"})
    if existing:
        for field, value in values.items():
            setattr(existing, field, value)
        item = existing
    else:
        item = AyurvedicSource(source_id=source.id, **values)
        db.add(item)
    record_audit(db, actor_user_id=admin.id, action="ayurveda_source.upsert", resource_type="knowledge_source", resource_id=source.id)
    db.commit()
    return SourceResponse.model_validate(source_payload(source))


@router.get("/guidelines", response_model=list[GuidelineResponse])
def list_guidelines(admin: AdminUser, db: DBSession) -> list[GuidelineResponse]:
    items = db.execute(select(Guideline).order_by(Guideline.updated_at.desc())).scalars().all()
    return [
        GuidelineResponse(
            id=item.id,
            authority=item.authority,
            jurisdiction=item.jurisdiction,
            version=item.source.version,
            effective_date=item.effective_date,
            review_due_date=item.review_due_date,
            status=_guideline_status(item),
            source=SourceResponse.model_validate(source_payload(item.source)),
        )
        for item in items
    ]


@router.post("/guidelines", response_model=GuidelineResponse, status_code=status.HTTP_201_CREATED)
def create_guideline(payload: GuidelineRequest, admin: AdminUser, db: DBSession) -> GuidelineResponse:
    source = db.get(KnowledgeSource, payload.source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")
    if payload.status == "active" and source.review_status != ReviewStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an approved source can be an active guideline")
    existing = db.execute(select(Guideline).where(Guideline.source_id == source.id)).scalar_one_or_none()
    values = payload.model_dump(exclude={"source_id"})
    if existing:
        for field, value in values.items():
            setattr(existing, field, value)
        item = existing
    else:
        item = Guideline(source_id=source.id, **values)
        db.add(item)
    db.flush()
    record_audit(db, actor_user_id=admin.id, action="guideline.upsert", resource_type="guideline", resource_id=item.id)
    db.commit()
    return GuidelineResponse(
        id=item.id,
        authority=item.authority,
        jurisdiction=item.jurisdiction,
        version=source.version,
        effective_date=item.effective_date,
        review_due_date=item.review_due_date,
        status=_guideline_status(item),
        source=SourceResponse.model_validate(source_payload(source)),
    )


@router.put("/guidelines/{guideline_id}", response_model=GuidelineResponse)
def update_guideline(guideline_id: str, payload: GuidelineRequest, admin: AdminUser, db: DBSession) -> GuidelineResponse:
    item = db.get(Guideline, guideline_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guideline not found")
    source = item.source
    if payload.status == "active" and source.review_status != ReviewStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an approved source can be an active guideline")
    for field, value in payload.model_dump(exclude={"source_id"}).items():
        setattr(item, field, value)
    record_audit(db, actor_user_id=admin.id, action="guideline.update", resource_type="guideline", resource_id=item.id)
    db.commit()
    return GuidelineResponse(
        id=item.id,
        authority=item.authority,
        jurisdiction=item.jurisdiction,
        version=source.version,
        effective_date=item.effective_date,
        review_due_date=item.review_due_date,
        status=_guideline_status(item),
        source=SourceResponse.model_validate(source_payload(source)),
    )
