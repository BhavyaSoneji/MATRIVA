"""Manual live verification for #5 (Gemini embeddings + pgvector storage).

Not a pytest file -- this needs a real Postgres+pgvector instance, which CI
doesn't have. Run this yourself against `docker compose up -d db` (or any
Postgres+pgvector instance) before trusting PgVectorStore in production; the
unit tests in tests/test_vector_store.py only exercise the same logic
against InMemoryVectorStore.

Usage:
    export DATABASE_URL=postgresql+psycopg://matriva:matriva@localhost:5432/matriva
    cd backend && python scripts/verify_pgvector_live.py

Uses synthetic embedding vectors (not real Gemini output) -- this verifies
the pgvector storage/query/re-indexing mechanics, not embedding quality.
Embedding generation itself (app/rag/embeddings.py) still needs a real
EMBEDDING_API_KEY to verify separately; see embed_text()'s docstring.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import sessionmaker

from app.core.db import engine
from app.models.knowledge import KnowledgeChunkRecord, RagBase
from app.rag.vector_store import PgVectorStore
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk


def make_chunk(chunk_id: str, document_id: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        source_id="src-1",
        domain=Domain.NUTRITION,
        evidence_level=EvidenceLevel.SUPPORTED,
        content=f"content for {chunk_id}",
        chunk_index=0,
    )


def main() -> None:
    print("Creating rag_knowledge_chunks table (if not present)...")
    RagBase.metadata.create_all(engine, tables=[KnowledgeChunkRecord.__table__])

    session_factory = sessionmaker(bind=engine)
    store = PgVectorStore(session_factory)

    print("Storing chunk with a real pgvector embedding column...")
    near_chunk = make_chunk("near", "doc-live-1")
    far_chunk = make_chunk("far", "doc-live-2")
    store.upsert_document("doc-live-1", [(near_chunk, [1.0, 0.0, 0.0] + [0.0] * 765)])
    store.upsert_document("doc-live-2", [(far_chunk, [0.0, 1.0, 0.0] + [0.0] * 765)])

    print("Querying nearest neighbor via real pgvector cosine_distance SQL...")
    results = store.query([0.9, 0.1, 0.0] + [0.0] * 765, k=2)
    assert results[0][0].chunk_id == "near", f"expected 'near' first, got {results[0][0].chunk_id}"
    print(f"  OK: nearest neighbor is {results[0][0].chunk_id!r} (score={results[0][1]:.4f})")

    print("Verifying re-indexing (old embeddings must not remain active)...")
    store.upsert_document("doc-live-1", [(make_chunk("near-v2", "doc-live-1"), [1.0, 0.0, 0.0] + [0.0] * 765)])
    results = store.query([0.9, 0.1, 0.0] + [0.0] * 765, k=10)
    ids = {chunk.chunk_id for chunk, _ in results}
    assert "near" not in ids, "old chunk_id 'near' should have been replaced by re-indexing"
    assert "near-v2" in ids
    print(f"  OK: re-indexing replaced old chunk, current ids = {ids}")

    print("\nAll live pgvector checks passed.")


if __name__ == "__main__":
    main()
