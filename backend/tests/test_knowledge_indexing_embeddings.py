"""reindex_document should populate real embeddings when a key is
configured, so retrieve_chunks_scored can actually do vector search for
documents uploaded through the admin API -- not just the eval scripts."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
    ReviewStatus,
    User,
)
from app.services import knowledge as knowledge_module
from app.services.knowledge import reindex_document


def _chunks_for(db, document_id: str) -> list[KnowledgeChunk]:
    return list(db.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)).scalars())


def _make_document(db) -> KnowledgeDocument:
    user = User(email="indexer@example.com", password_hash="x", full_name="Indexer")
    db.add(user)
    db.flush()
    source = KnowledgeSource(
        name="src-indexing",
        title="Test source",
        source_type="government",
        review_status=ReviewStatus.APPROVED.value,
        evidence_level="supported",
    )
    db.add(source)
    db.flush()
    document = KnowledgeDocument(
        source_id=source.id,
        title="Indexing test document",
        domain="nutrition",
        language="en",
        review_status=ReviewStatus.PENDING.value,
        index_status="pending",
        content_hash="hash-indexing",
        file_name="test.txt",
        mime_type="text/plain",
        raw_content=b"First paragraph about nutrition.\n\nSecond paragraph about lifestyle.",
        active=False,
        created_by=user.id,
    )
    db.add(document)
    db.flush()
    return document


@pytest.fixture(autouse=True)
def _no_key_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_chunks_have_no_embedding_without_api_key(client) -> None:
    with SessionLocal() as db:
        document = _make_document(db)
        reindex_document(db, document)
        db.commit()
        assert all(chunk.embedding is None for chunk in _chunks_for(db, document.id))


def test_chunks_get_real_embeddings_when_api_key_configured(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setattr(
        knowledge_module,
        "embed_chunk_contents",
        lambda contents, api_key=None: [[0.1, 0.2, 0.3] for _ in contents],
    )
    with SessionLocal() as db:
        document = _make_document(db)
        count = reindex_document(db, document)
        db.commit()
        chunks = _chunks_for(db, document.id)
        assert count == len(chunks) > 0
        assert all(chunk.embedding == [0.1, 0.2, 0.3] for chunk in chunks)


def test_reindex_still_succeeds_when_embedding_provider_fails(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")

    def _boom(contents, api_key=None):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(knowledge_module, "embed_chunk_contents", _boom)
    with SessionLocal() as db:
        document = _make_document(db)
        count = reindex_document(db, document)
        db.commit()
        assert count > 0
        assert document.index_status == "indexed"
        assert all(chunk.embedding is None for chunk in _chunks_for(db, document.id))
