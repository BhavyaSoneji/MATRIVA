"""Hybrid retrieval (issue #6, Master Prompt Section 12 Step 6 + Section 13).

Combines semantic vector search + metadata filtering + keyword search. Section
13: don't over-filter in a way that removes important general medical
information -- so metadata filters here are lenient (a chunk with no
pregnancy_stage/region set is treated as universally applicable, not
excluded) and, per this issue's acceptance criteria, retrieval falls back to
the unfiltered candidate pool if filtering would otherwise return nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import dataclass as DatabaseDataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DatabaseSession

from app.models import KnowledgeChunk as KnowledgeChunkRow
from app.models import KnowledgeDocument as KnowledgeDocumentRow
from app.models import KnowledgeSource as KnowledgeSourceRow
from app.models import ReviewStatus as ReviewStatusValue
from app.rag.keyword_search import keyword_overlap_score
from app.rag.vector_store import VectorStore
from app.schemas.knowledge import Domain, KnowledgeChunk

DEFAULT_POOL_SIZE = 20
KEYWORD_WEIGHT = 0.1  # small boost relative to vector similarity, not a replacement for it


@dataclass
class RetrievalResult:
    chunks: list[tuple[KnowledgeChunk, float]]
    used_fallback: bool


def apply_metadata_filters(
    chunks: list[KnowledgeChunk],
    *,
    pregnancy_stage: str | None = None,
    domains: list[Domain] | None = None,
    region: str | None = None,
) -> list[KnowledgeChunk]:
    """Section 13 example: pregnancy_stage AND domain IN (...) AND region.

    Lenient by design: a chunk missing a given metadata field, or tagged
    "all" for that field, is treated as applicable rather than excluded --
    over-filtering could remove important general medical information.
    """

    def stage_ok(chunk: KnowledgeChunk) -> bool:
        return (
            pregnancy_stage is None
            or chunk.pregnancy_stage in (None, "all", pregnancy_stage)
        )

    def domain_ok(chunk: KnowledgeChunk) -> bool:
        return domains is None or chunk.domain in domains

    def region_ok(chunk: KnowledgeChunk) -> bool:
        return region is None or chunk.region in (None, region)

    return [c for c in chunks if stage_ok(c) and domain_ok(c) and region_ok(c)]


def hybrid_retrieve(
    query: str,
    *,
    query_embedding: list[float] | None = None,
    vector_store: VectorStore | None = None,
    candidate_chunks: list[KnowledgeChunk] | None = None,
    candidate_scores: dict[str, float] | None = None,
    pregnancy_stage: str | None = None,
    domains: list[Domain] | None = None,
    region: str | None = None,
    k: int = 5,
    pool_size: int = DEFAULT_POOL_SIZE,
) -> RetrievalResult:
    """Retrieve a filtered candidate set for `query` + user context.

    Provide either `vector_store` + `query_embedding` (real semantic search),
    or `candidate_chunks` alone (keyword-only path -- useful when no
    embedding is available yet, same situation Sprint 0's seed_qa.py handles
    for #66). If both are given, vector-search candidates are used and
    keyword score is blended in as a secondary signal.
    """
    if vector_store is not None and query_embedding is not None:
        pool = vector_store.query(query_embedding, k=pool_size)
    elif candidate_chunks is not None:
        scores = candidate_scores or {}
        pool = [(chunk, float(scores.get(chunk.chunk_id, 0.0))) for chunk in candidate_chunks]
    else:
        raise ValueError("Provide either (vector_store + query_embedding) or candidate_chunks")

    scored = [
        (chunk, base_score + KEYWORD_WEIGHT * keyword_overlap_score(query, chunk.content))
        for chunk, base_score in pool
    ]

    filtered = apply_metadata_filters(
        [c for c, _ in scored], pregnancy_stage=pregnancy_stage, domains=domains, region=region
    )
    filtered_ids = {c.chunk_id for c in filtered}
    filtered_scored = [pair for pair in scored if pair[0].chunk_id in filtered_ids]

    used_fallback = False
    result_pool = filtered_scored
    if not result_pool and scored:
        # Section 13: don't let filtering silently return nothing when the
        # unfiltered pool had relevant candidates.
        used_fallback = True
        result_pool = scored

    result_pool.sort(key=lambda pair: pair[1], reverse=True)
    return RetrievalResult(chunks=result_pool[:k], used_fallback=used_fallback)


# --- SQLAlchemy/API retrieval adapter -------------------------------------
# The RAG evaluation pipeline above consumes the canonical Pydantic chunks.
# The HTTP API persists the same concepts in SQLAlchemy rows, so this adapter
# performs approval/staleness checks before exposing rows to the service layer.


@DatabaseDataclass(frozen=True)
class RetrievedChunk:
    chunk: KnowledgeChunkRow
    document: KnowledgeDocumentRow
    source: KnowledgeSourceRow
    score: float


_WORD_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)
_STOPWORDS = {
    "a", "an", "and", "are", "do", "during", "for", "how", "i", "in", "is", "it", "me", "my",
    "of", "on", "the", "to", "what", "when", "with", "pregnancy", "woman", "women",
}


def tokenize(value: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(value)
        if len(token) > 1 and token.lower() not in _STOPWORDS
    }


def score_text(query: str, content: str) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    content_tokens = tokenize(content)
    overlap = len(query_tokens & content_tokens)
    if not overlap:
        return 0.0
    phrase_bonus = 0.25 if query.strip().lower() in content.lower() else 0.0
    return (overlap / len(query_tokens)) + phrase_bonus


def retrieve_chunks(
    db: DatabaseSession,
    query: str,
    *,
    domain: str | None = None,
    stage: str | None = None,
    region: str | None = None,
    source_type: str | None = None,
    evidence_level: str | None = None,
    limit: int = 8,
) -> list[RetrievedChunk]:
    statement = (
        select(KnowledgeChunkRow, KnowledgeDocumentRow, KnowledgeSourceRow)
        .join(KnowledgeDocumentRow, KnowledgeChunkRow.document_id == KnowledgeDocumentRow.id)
        .join(KnowledgeSourceRow, KnowledgeChunkRow.source_id == KnowledgeSourceRow.id)
        .where(
            KnowledgeDocumentRow.active.is_(True),
            KnowledgeDocumentRow.review_status == ReviewStatusValue.APPROVED.value,
            KnowledgeSourceRow.review_status == ReviewStatusValue.APPROVED.value,
        )
    )
    if domain:
        statement = statement.where(KnowledgeDocumentRow.domain == domain)
    if source_type:
        statement = statement.where(KnowledgeSourceRow.source_type == source_type)
    if evidence_level:
        statement = statement.where(KnowledgeSourceRow.evidence_level == evidence_level)
    if stage:
        statement = statement.where(
            or_(KnowledgeDocumentRow.pregnancy_stage == stage, KnowledgeDocumentRow.pregnancy_stage.is_(None))
        )
    if region:
        statement = statement.where(
            or_(
                KnowledgeDocumentRow.region == region,
                KnowledgeDocumentRow.region.is_(None),
                KnowledgeSourceRow.jurisdiction == "India",
            )
        )
    statement = statement.order_by(KnowledgeChunkRow.chunk_index).limit(250)
    rows = db.execute(statement).all()
    scored: list[RetrievedChunk] = []
    for chunk, document, source in rows:
        guideline = source.guideline
        if guideline is not None:
            stale = (
                guideline.review_due_date is not None
                and guideline.review_due_date < datetime.now(timezone.utc).date()
            )
            if guideline.status != "active" or stale:
                continue
        searchable_text = " ".join(
            str(value or "")
            for value in (chunk.content, document.title, document.domain, document.subdomain, source.topic)
        )
        scored.append(
            RetrievedChunk(chunk=chunk, document=document, source=source, score=score_text(query, searchable_text))
        )
    if query.strip():
        scored = [item for item in scored if item.score > 0]
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[: max(1, min(limit, 25))]


def build_context(chunks: list[RetrievedChunk]) -> str:
    """Build a data-only context packet; retrieved text is never instructions."""

    sections: list[str] = []
    for index, item in enumerate(chunks, start=1):
        source = item.source
        metadata = source.extra_metadata or {}
        sections.append(
            "\n".join(
                [
                    f"[EVIDENCE {index}]",
                    f"source_id={source.id}",
                    f"source_name={source.name}",
                    f"source_type={source.source_type}",
                    f"evidence_level={source.evidence_level}",
                    f"locator={metadata.get('page_or_section') or metadata.get('locator') or 'not provided'}",
                    "BEGIN_UNTRUSTED_EVIDENCE",
                    item.chunk.content,
                    "END_UNTRUSTED_EVIDENCE",
                ]
            )
        )
    return "\n\n".join(sections)
