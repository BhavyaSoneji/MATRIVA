from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Guideline,
    KnowledgeDocument,
    KnowledgeSource,
    ReviewStatus,
)


def source_payload(source: KnowledgeSource) -> dict[str, Any]:
    evidence = source.evidence_metadata
    guideline = source.guideline
    ayurveda = source.ayurvedic_source
    extra = dict(source.extra_metadata or {})
    if ayurveda:
        extra.setdefault("ayurvedic_provenance", {
            "book": ayurveda.book,
            "chapter": ayurveda.chapter,
            "verse_or_page": ayurveda.verse_or_page,
            "original_text": ayurveda.original_text,
            "translation": ayurveda.translation,
            "interpretation": ayurveda.interpretation,
            "traditional_context": ayurveda.traditional_context,
            "evidence_label": ayurveda.evidence_label,
        })
    if guideline:
        extra.setdefault("guideline", {
            "authority": guideline.authority,
            "jurisdiction": guideline.jurisdiction,
            "effective_date": guideline.effective_date.isoformat() if guideline.effective_date else None,
            "review_due_date": guideline.review_due_date.isoformat() if guideline.review_due_date else None,
            "status": guideline.status,
            "scope_notes": guideline.scope_notes,
        })
    return {
        "id": source.id,
        "name": source.name,
        "title": source.title,
        "source_type": source.source_type,
        "authority": source.authority,
        "jurisdiction": source.jurisdiction,
        "topic": source.topic,
        "url": source.url,
        "version": source.version,
        "publication_date": source.publication_date,
        "review_status": source.review_status,
        "evidence_level": source.evidence_level,
        "evidence_label": evidence.evidence_label if evidence else None,
        "page_or_section": extra.get("page_or_section") or extra.get("locator"),
        "extra_metadata": extra,
    }


def get_source(db: Session, source_id: str, *, include_pending: bool = False) -> KnowledgeSource | None:
    source = db.get(KnowledgeSource, source_id)
    if source is None:
        return None
    if not include_pending and source.review_status != ReviewStatus.APPROVED.value:
        return None
    return source


def get_document(db: Session, document_id: str, *, include_pending: bool = False) -> KnowledgeDocument | None:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        return None
    if not include_pending and (not document.active or document.review_status != ReviewStatus.APPROVED.value):
        return None
    return document


def list_guidelines(db: Session) -> list[Guideline]:
    return list(db.execute(select(Guideline).where(Guideline.status == "active")).scalars().all())
