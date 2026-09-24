"""Tests for the real-embeddings retrieval path wired into the live API
(issue: chat/API should use real RAG, not just the eval scripts)."""

from __future__ import annotations

import pytest

from app.core.db import SessionLocal
from app.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
    ReviewStatus,
    User,
)
from app.rag import retrieval as retrieval_module
from app.rag.retrieval import retrieve_chunks_scored


def _make_document(db, *, with_embedding: bool) -> None:
    user = User(email="tester@example.com", password_hash="x", full_name="Tester")
    db.add(user)
    db.flush()
    source = KnowledgeSource(
        name="src-1",
        title="Test source",
        source_type="government",
        review_status=ReviewStatus.APPROVED.value,
        evidence_level="supported",
    )
    db.add(source)
    db.flush()
    document = KnowledgeDocument(
        source_id=source.id,
        title="Test document",
        domain="nutrition",
        language="en",
        review_status=ReviewStatus.APPROVED.value,
        index_status="indexed",
        content_hash="hash",
        file_name="test.txt",
        mime_type="text/plain",
        raw_content=b"demo",
        active=True,
        created_by=user.id,
    )
    db.add(document)
    db.flush()
    db.add(
        KnowledgeChunk(
            document_id=document.id,
            source_id=source.id,
            chunk_index=0,
            content="Balanced meals during pregnancy include a variety of food groups.",
            embedding=[1.0, 0.0, 0.0] if with_embedding else None,
        )
    )
    db.commit()


@pytest.fixture(autouse=True)
def _no_key_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_falls_back_to_keyword_without_api_key(client) -> None:
    with SessionLocal() as db:
        _make_document(db, with_embedding=True)
        chunks, mode = retrieve_chunks_scored(db, "balanced meals pregnancy")
        assert mode == "keyword"
        assert chunks


def test_falls_back_to_keyword_when_a_chunk_has_no_embedding(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    with SessionLocal() as db:
        _make_document(db, with_embedding=False)
        chunks, mode = retrieve_chunks_scored(db, "balanced meals pregnancy")
        assert mode == "keyword"
        assert chunks


def test_uses_vector_mode_when_key_set_and_all_chunks_embedded(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setattr(retrieval_module, "embed_text", lambda text, api_key=None: [1.0, 0.0, 0.0])
    with SessionLocal() as db:
        _make_document(db, with_embedding=True)
        chunks, mode = retrieve_chunks_scored(db, "balanced meals pregnancy")
        assert mode == "vector"
        assert len(chunks) == 1
        assert chunks[0].score == pytest.approx(1.0)


def test_vector_mode_falls_back_to_keyword_on_embedding_provider_failure(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")

    def _boom(text: str, api_key: str | None = None) -> list[float]:
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(retrieval_module, "embed_text", _boom)
    with SessionLocal() as db:
        _make_document(db, with_embedding=True)
        chunks, mode = retrieve_chunks_scored(db, "balanced meals pregnancy")
        assert mode == "keyword"
        assert chunks
