"""Vector storage + re-indexing + nearest-neighbor query (issue #5).

Two implementations of the same interface:

- `InMemoryVectorStore`: pure-Python cosine similarity, no DB required. Used
  for unit tests here and as a local/dev fallback, the same pattern Sprint 0's
  seed_qa.py used for keyword-overlap retrieval ahead of real infra.
- `PgVectorStore`: the real Section 15 implementation against Postgres +
  pgvector. **Not integration-tested in this environment** -- there's no live
  Postgres+pgvector instance available here. Its query logic is identical to
  `InMemoryVectorStore`'s (same re-indexing contract, same top-k-by-similarity
  shape), just expressed as a pgvector SQL query instead of a Python loop, so
  `InMemoryVectorStore`'s test coverage stands in for the *logic*; someone
  with a running `docker compose up db` should still run one real end-to-end
  check before this is considered fully verified per the issue's acceptance
  criteria.

Re-indexing contract (Section 15): when a document changes, old embeddings
for that document must not silently remain active. Both implementations
enforce this the same way -- `upsert_document` replaces the *entire* set of
chunks for a document_id, never appends alongside stale ones.
"""

from __future__ import annotations

import math
from typing import Protocol

from app.schemas.knowledge import KnowledgeChunk


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorStore(Protocol):
    def upsert_document(
        self, document_id: str, chunks_with_embeddings: list[tuple[KnowledgeChunk, list[float]]]
    ) -> None: ...

    def query(
        self, embedding: list[float], *, k: int = 5, domain: str | None = None
    ) -> list[tuple[KnowledgeChunk, float]]: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._by_document: dict[str, list[tuple[KnowledgeChunk, list[float]]]] = {}

    def upsert_document(
        self, document_id: str, chunks_with_embeddings: list[tuple[KnowledgeChunk, list[float]]]
    ) -> None:
        """Replace this document's chunks entirely -- old embeddings for
        `document_id` are discarded, never left active alongside new ones."""
        self._by_document[document_id] = list(chunks_with_embeddings)

    def query(
        self, embedding: list[float], *, k: int = 5, domain: str | None = None
    ) -> list[tuple[KnowledgeChunk, float]]:
        candidates = [
            (chunk, score)
            for chunks in self._by_document.values()
            for chunk, vec in chunks
            if domain is None or chunk.domain == domain
            for score in [cosine_similarity(embedding, vec)]
        ]
        candidates.sort(key=lambda pair: pair[1], reverse=True)
        return candidates[:k]

    @property
    def chunk_count(self) -> int:
        return sum(len(chunks) for chunks in self._by_document.values())


class PgVectorStore:
    """Section 15 production implementation. Requires a live Postgres +
    pgvector instance -- not exercised in this environment (no DB running
    here). See module docstring."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def upsert_document(
        self, document_id: str, chunks_with_embeddings: list[tuple[KnowledgeChunk, list[float]]]
    ) -> None:
        from app.models.knowledge import KnowledgeChunkRecord

        with self._session_factory() as session:
            session.query(KnowledgeChunkRecord).filter(
                KnowledgeChunkRecord.document_id == document_id
            ).delete()
            session.add_all(
                [
                    KnowledgeChunkRecord(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        source_id=chunk.source_id,
                        domain=chunk.domain,
                        topic=chunk.topic,
                        pregnancy_stage=chunk.pregnancy_stage,
                        evidence_level=chunk.evidence_level,
                        region=chunk.region,
                        language=chunk.language,
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        token_count=chunk.token_count,
                        embedding=embedding,
                    )
                    for chunk, embedding in chunks_with_embeddings
                ]
            )
            session.commit()

    def query(
        self, embedding: list[float], *, k: int = 5, domain: str | None = None
    ) -> list[tuple[KnowledgeChunk, float]]:
        from app.models.knowledge import KnowledgeChunkRecord

        with self._session_factory() as session:
            q = session.query(KnowledgeChunkRecord)
            if domain is not None:
                q = q.filter(KnowledgeChunkRecord.domain == domain)
            rows = q.order_by(KnowledgeChunkRecord.embedding.cosine_distance(embedding)).limit(k).all()
            return [
                (
                    KnowledgeChunk(
                        chunk_id=row.chunk_id,
                        document_id=row.document_id,
                        source_id=row.source_id,
                        domain=row.domain,
                        topic=row.topic,
                        pregnancy_stage=row.pregnancy_stage,
                        evidence_level=row.evidence_level,
                        region=row.region,
                        language=row.language,
                        content=row.content,
                        chunk_index=row.chunk_index,
                        token_count=row.token_count,
                    ),
                    cosine_similarity(embedding, list(row.embedding)),
                )
                for row in rows
            ]
