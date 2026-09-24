"""Knowledge document & chunk schema (issue #1).

Data model for `knowledge_documents`, `knowledge_chunks`, and Ayurvedic provenance
per Master Prompt Section 9 (KNOWLEDGE DOCUMENT MODEL), Section 10 (KNOWLEDGE DOMAINS),
Section 11 (AYURVEDA DATA RULE), and Section 14 (CHUNKING STRATEGY).

These are ingestion/application-layer Pydantic models, not the SQLAlchemy ORM models
(those live in app/models once #24 backend DB work picks this up) -- this issue only
covers the schema shape the ingestion pipeline (#2-#4) and ORM models build against.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Domain(StrEnum):
    """Section 10: the 5 knowledge domains."""

    MODERN_MEDICAL = "MODERN_MEDICAL"
    AYURVEDA = "AYURVEDA"
    NUTRITION = "NUTRITION"
    LIFESTYLE = "LIFESTYLE"
    REGIONAL_CULTURAL = "REGIONAL_CULTURAL"


class SourceType(StrEnum):
    """Section 9 example source types. DO NOT invent sources outside a real, cited
    document -- this enum constrains *type*, not which specific sources exist."""

    MEDICAL_GUIDELINE = "medical_guideline"
    CLINICAL_REFERENCE = "clinical_reference"
    TEXTBOOK = "textbook"
    AYURVEDIC_CLASSICAL_SOURCE = "ayurvedic_classical_source"
    TRADITIONAL_REFERENCE = "traditional_reference"
    NUTRITION_REFERENCE = "nutrition_reference"
    INSTITUTIONAL_GUIDANCE = "institutional_guidance"


class EvidenceLevel(StrEnum):
    """Section 11: the only evidence-label vocabulary the Master Prompt defines.
    Applies across all domains, not just Ayurveda -- Section 9 and Section 14 both
    reference a generic `evidence_level` field with no separate enum of their own.

    Only use a label that can actually be justified by the curated source/reviewer;
    do not default to SUPPORTED just because a source looks authoritative.
    """

    TRADITIONAL = "TRADITIONAL"
    PRELIMINARY = "PRELIMINARY"
    LIMITED_EVIDENCE = "LIMITED_EVIDENCE"
    MIXED_EVIDENCE = "MIXED_EVIDENCE"
    SUPPORTED = "SUPPORTED"
    UNCERTAIN = "UNCERTAIN"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class ReviewStatus(StrEnum):
    """Not explicitly enumerated in the Master Prompt beyond "mark it UNVERIFIED"
    (Section 9). UNVERIFIED is that generic state; the PENDING_* values are this
    project's refinement so ingestion/review tooling can distinguish *why* something
    isn't cleared yet (see knowledge/seed/seed.yaml for real usage)."""

    UNVERIFIED = "UNVERIFIED"
    PENDING_SOURCE_VERIFICATION = "PENDING_SOURCE_VERIFICATION"
    PENDING_CLINICAL_REVIEW = "PENDING_CLINICAL_REVIEW"
    REVIEWED_APPROVED = "REVIEWED_APPROVED"
    REJECTED = "REJECTED"


class AyurvedicProvenance(BaseModel):
    """Section 11: for every Ayurvedic source, retain full provenance. Traditional
    knowledge must NEVER be silently converted into a modern medical claim -- this
    model exists so that conversion can never happen implicitly; `modern_evidence_status`
    must be set explicitly and separately from the traditional content itself."""

    source: str
    book: str
    chapter: str | None = None
    verse_or_page: str | None = None
    original_text: str
    translation: str | None = None
    interpretation: str | None = None
    traditional_context: str | None = None
    modern_evidence_status: EvidenceLevel


class KnowledgeDocument(BaseModel):
    """Section 9: KNOWLEDGE DOCUMENT MODEL."""

    document_id: str
    title: str
    content: str
    domain: Domain
    subdomain: str | None = None
    source_id: str
    source_type: SourceType
    publication_date: str | None = None
    version: str = "1.0"
    language: str = "en"
    region: str | None = None
    pregnancy_stage: str | None = None
    topic: str | None = None
    evidence_level: EvidenceLevel
    review_status: ReviewStatus = ReviewStatus.UNVERIFIED
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    safety_tags: list[str] = Field(default_factory=list)

    # Present only when domain == AYURVEDA (Section 11 provenance requirement).
    ayurvedic_provenance: AyurvedicProvenance | None = None

    def model_post_init(self, context: object, /) -> None:
        if self.domain == Domain.AYURVEDA and self.ayurvedic_provenance is None:
            raise ValueError(
                "AYURVEDA documents must carry ayurvedic_provenance (Master Prompt Section 11)"
            )


class KnowledgeChunk(BaseModel):
    """Section 14: CHUNKING STRATEGY per-chunk metadata. 300-700 tokens per chunk,
    structure-preserving (heading/section/source/page/paragraph relationship) --
    chunking itself is #3; this is just the chunk's required shape."""

    chunk_id: str
    document_id: str
    source_id: str
    domain: Domain
    topic: str | None = None
    pregnancy_stage: str | None = None
    evidence_level: EvidenceLevel
    region: str | None = None
    language: str = "en"

    # Practical additions the spec assumes but doesn't spell out: chunks need
    # actual text and a position within the parent document.
    content: str
    chunk_index: int
    token_count: int | None = None
