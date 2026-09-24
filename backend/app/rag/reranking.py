"""Reranking stage (issue #7, Master Prompt Section 12 Step 7).

Rerank retrieved chunks by: semantic relevance (carried in as `base_score`
from #6's hybrid_retrieve), pregnancy-stage relevance, source quality,
evidence level, regional relevance, and user context.

`source_quality` reflects documentation rigor/formality of the source TYPE
(e.g. a formal medical guideline vs. an informal traditional reference), not
domain legitimacy -- Section 11 is explicit that traditional/Ayurvedic
knowledge must never be treated as lower-value than modern medical content,
so this signal is weighted modestly and evidence_level is scored on
confidence-for-its-own-claim-type, not a modern-vs-traditional hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.rag.keyword_search import keyword_overlap_score
from app.schemas.knowledge import EvidenceLevel, KnowledgeChunk, SourceType

# Documentation rigor/formality, not domain legitimacy (see module docstring).
SOURCE_QUALITY_WEIGHT: dict[SourceType, float] = {
    SourceType.MEDICAL_GUIDELINE: 1.0,
    SourceType.INSTITUTIONAL_GUIDANCE: 1.0,
    SourceType.CLINICAL_REFERENCE: 0.9,
    SourceType.TEXTBOOK: 0.8,
    SourceType.AYURVEDIC_CLASSICAL_SOURCE: 0.8,
    SourceType.NUTRITION_REFERENCE: 0.7,
    SourceType.TRADITIONAL_REFERENCE: 0.6,
}

# Confidence associated with the evidence label itself, not a
# modern-vs-traditional ranking -- TRADITIONAL and SUPPORTED are both
# well-supported *for what they claim*; UNCERTAIN/NOT_ESTABLISHED are not.
EVIDENCE_LEVEL_WEIGHT: dict[EvidenceLevel, float] = {
    EvidenceLevel.SUPPORTED: 1.0,
    EvidenceLevel.TRADITIONAL: 0.9,
    EvidenceLevel.PRELIMINARY: 0.6,
    EvidenceLevel.MIXED_EVIDENCE: 0.5,
    EvidenceLevel.LIMITED_EVIDENCE: 0.4,
    EvidenceLevel.UNCERTAIN: 0.2,
    EvidenceLevel.NOT_ESTABLISHED: 0.1,
}

STAGE_WEIGHT = 0.3
SOURCE_QUALITY_SCALE = 0.15
EVIDENCE_WEIGHT = 0.2
REGION_WEIGHT = 0.2
CONTEXT_WEIGHT = 0.05


@dataclass
class UserContext:
    pregnancy_stage: str | None = None
    region: str | None = None
    context_terms: list[str] = field(default_factory=list)  # e.g. diet/preference keywords


def _stage_relevance(chunk: KnowledgeChunk, context: UserContext) -> float:
    if context.pregnancy_stage is None or chunk.pregnancy_stage is None:
        return 0.0
    if chunk.pregnancy_stage in (context.pregnancy_stage, "all"):
        return 1.0
    return 0.0


def _region_relevance(chunk: KnowledgeChunk, context: UserContext) -> float:
    if context.region is None or chunk.region is None:
        return 0.0
    return 1.0 if chunk.region == context.region else 0.0


def _context_relevance(chunk: KnowledgeChunk, context: UserContext) -> float:
    if not context.context_terms:
        return 0.0
    overlap = keyword_overlap_score(" ".join(context.context_terms), chunk.content)
    return min(overlap / max(len(context.context_terms), 1), 1.0)


def rerank(
    scored_chunks: list[tuple[KnowledgeChunk, float]],
    context: UserContext | None = None,
    *,
    source_types: dict[str, SourceType] | None = None,
) -> list[tuple[KnowledgeChunk, float]]:
    """Combine semantic relevance (`base_score`, from #6) with stage/source
    quality/evidence/region/user-context signals into a final ranked list.

    `KnowledgeChunk` (#1) doesn't carry `source_type` itself -- only the
    parent `KnowledgeDocument` does -- so `source_types` maps `source_id` to
    the document's `SourceType` for chunks where that's known. Chunks whose
    source isn't in the map get a neutral default quality score.
    """
    context = context or UserContext()
    source_types = source_types or {}

    reranked = []
    for chunk, base_score in scored_chunks:
        source_type = source_types.get(chunk.source_id)
        source_quality = SOURCE_QUALITY_WEIGHT.get(source_type, 0.7)
        evidence_weight = EVIDENCE_LEVEL_WEIGHT.get(chunk.evidence_level, 0.5)

        final_score = (
            base_score
            + STAGE_WEIGHT * _stage_relevance(chunk, context)
            + SOURCE_QUALITY_SCALE * source_quality
            + EVIDENCE_WEIGHT * evidence_weight
            + REGION_WEIGHT * _region_relevance(chunk, context)
            + CONTEXT_WEIGHT * _context_relevance(chunk, context)
        )
        reranked.append((chunk, final_score))

    reranked.sort(key=lambda pair: pair[1], reverse=True)
    return reranked
