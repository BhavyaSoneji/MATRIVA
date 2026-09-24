from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DBSession
from app.models import (
    ExerciseGuidance,
    FoodItem,
    Guideline,
)
from app.rag.retrieval import retrieve_chunks
from app.repositories.knowledge import get_source, source_payload
from app.schemas.api import (
    GuidelineResponse,
    KnowledgeResult,
    KnowledgeSearchResponse,
    SourceResponse,
)

router = APIRouter(tags=["knowledge"])


def _guideline_status(status_value: str, review_due_date) -> str:
    if review_due_date is not None and review_due_date < datetime.now(timezone.utc).date():
        return "stale"
    return status_value


@router.get("/knowledge/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    db: DBSession,
    query: str = Query(default="", max_length=500),
    domain: str | None = Query(default=None, max_length=80),
    pregnancy_stage: str | None = Query(default=None, max_length=40),
    region: str | None = Query(default=None, max_length=80),
    source_type: str | None = Query(default=None, max_length=40),
    evidence_level: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=10, ge=1, le=25),
) -> KnowledgeSearchResponse:
    retrieved = retrieve_chunks(
        db,
        query,
        domain=domain,
        stage=pregnancy_stage,
        region=region,
        source_type=source_type,
        evidence_level=evidence_level,
        limit=limit,
    )
    results = [
        KnowledgeResult(
            chunk_id=item.chunk.id,
            document_id=item.document.id,
            document_title=item.document.title,
            domain=item.document.domain,
            subdomain=item.document.subdomain,
            region=item.document.region,
            pregnancy_stage=item.document.pregnancy_stage,
            content=item.chunk.content,
            score=round(item.score, 4),
            source=SourceResponse.model_validate(source_payload(item.source)),
        )
        for item in retrieved
    ]
    return KnowledgeSearchResponse(query=query, results=results, count=len(results))


@router.get("/sources/{source_id}", response_model=SourceResponse)
def get_source_details(source_id: str, db: DBSession) -> SourceResponse:
    source = get_source(db, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return SourceResponse.model_validate(source_payload(source))


@router.get("/ayurveda/sources/{source_id}", response_model=SourceResponse)
def get_ayurveda_source(source_id: str, db: DBSession) -> SourceResponse:
    source = get_source(db, source_id)
    if source is None or source.ayurvedic_source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ayurveda source not found")
    return SourceResponse.model_validate(source_payload(source))


@router.get("/guidelines", response_model=list[GuidelineResponse])
def list_guidelines(db: DBSession) -> list[GuidelineResponse]:
    guidelines = db.execute(select(Guideline).where(Guideline.status == "active")).scalars().all()
    return [
        GuidelineResponse(
            id=item.id,
            authority=item.authority,
            jurisdiction=item.jurisdiction,
            version=item.source.version,
            effective_date=item.effective_date,
            review_due_date=item.review_due_date,
            status=_guideline_status(item.status, item.review_due_date),
            source=SourceResponse.model_validate(source_payload(item.source)),
        )
        for item in guidelines
    ]


@router.get("/knowledge/food")
def search_food(
    db: DBSession,
    query: str = Query(default="", max_length=160),
    region: str | None = Query(default=None, max_length=80),
    diet: str | None = Query(default=None, max_length=40),
) -> list[dict[str, object]]:
    statement = select(FoodItem).where(FoodItem.active.is_(True))
    if region:
        statement = statement.where(FoodItem.region == region)
    if query:
        statement = statement.where(FoodItem.name.ilike(f"%{query}%"))
    items = db.execute(statement).scalars().all()
    result: list[dict[str, object]] = []
    for item in items:
        if query and query.lower() not in item.name.lower() and query.lower() not in {str(value).lower() for value in (item.local_names or [])}:
            continue
        if diet and diet.lower() not in {str(value).lower() for value in (item.dietary_types or [])}:
            continue
        result.append({
            "id": item.id,
            "name": item.name,
            "local_names": item.local_names,
            "region": item.region,
            "cuisine": item.cuisine,
            "ingredients": item.ingredients,
            "dietary_types": item.dietary_types,
            "nutrition_metadata": item.nutrition_metadata,
            "cultural_relevance": item.cultural_relevance,
            "pregnancy_context": item.pregnancy_context,
            "evidence_status": item.evidence_status,
            "safety_status": item.safety_status,
            "source_ids": item.source_ids,
        })
    return result


@router.get("/knowledge/lifestyle")
def list_lifestyle(
    db: DBSession,
    category: str | None = Query(default=None, max_length=60),
    pregnancy_stage: str | None = Query(default=None, max_length=40),
) -> list[dict[str, object]]:
    statement = select(ExerciseGuidance).where(ExerciseGuidance.active.is_(True))
    if category:
        statement = statement.where(ExerciseGuidance.category == category)
    items = db.execute(statement).scalars().all()
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
        }
        for item in items
        if not pregnancy_stage or pregnancy_stage in (item.suitable_stages or []) or not item.suitable_stages
    ]
