"""Hybrid retrieval (issue #6, Master Prompt Section 12 Step 6 + Section 13).

Combines semantic vector search + metadata filtering + keyword search. Section
13: don't over-filter in a way that removes important general medical
information -- so metadata filters here are lenient (a chunk with no
pregnancy_stage/region set is treated as universally applicable, not
excluded) and, per this issue's acceptance criteria, retrieval falls back to
the unfiltered candidate pool if filtering would otherwise return nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

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
        pool = [(chunk, 0.0) for chunk in candidate_chunks]
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
