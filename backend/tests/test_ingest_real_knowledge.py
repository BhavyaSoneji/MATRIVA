"""Tests for scripts/ingest_real_knowledge.py -- the real-content ingestion
pipeline for the book OCR and knowledge/seed/seed.yaml, wired into the live
SQL knowledge base rather than the eval-only RAG-core path.

The core safety property under test: everything this script inserts must be
review_status="pending", never "approved" -- it must not bypass the
retrieval gate on its own."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.ingest_real_knowledge as ingest_module
from app.core.db import SessionLocal
from app.models import (
    AyurvedicSource,
    FoodItem,
    Guideline,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)


@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_module, "embed_text", lambda text, api_key=None: [0.1, 0.2, 0.3])


def test_seed_yaml_ingests_all_documents_as_pending(client) -> None:
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)

        sources = db.query(KnowledgeSource).all()
        assert len(sources) == 8
        assert all(s.review_status == "pending" for s in sources)

        documents = db.query(KnowledgeDocument).all()
        assert len(documents) == 8
        assert all(d.review_status == "pending" and d.active is False for d in documents)

        chunks = db.query(KnowledgeChunk).all()
        assert len(chunks) == 8
        assert all(c.embedding == [0.1, 0.2, 0.3] for c in chunks)


def test_seed_yaml_creates_structured_side_records(client) -> None:
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)

        assert db.query(Guideline).count() == 1
        assert db.query(AyurvedicSource).count() == 2

        food_items = db.query(FoodItem).all()
        assert len(food_items) == 5
        # FoodItem has no review-status gate of its own (see /knowledge/food) --
        # must stay inactive until the source is approved, or nutrition data
        # would bypass the pending-review policy entirely.
        assert all(item.active is False for item in food_items)


def test_seed_yaml_ingestion_is_idempotent(client) -> None:
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)
        assert db.query(KnowledgeSource).count() == 8
        assert db.query(KnowledgeDocument).count() == 8


def test_pregnancy_stage_all_is_stored_as_null_not_literal_string(client) -> None:
    """retrieve_chunks_scored's stage filter treats NULL as "applies to every
    stage" -- storing the literal string "all" would instead exclude the
    document from every stage-specific query."""
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)
        anc_doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.title.contains("Antenatal")).one()
        assert anc_doc.pregnancy_stage is None


def test_book_ingestion_creates_one_pending_document_with_many_chunks(client, tmp_path, monkeypatch) -> None:
    # Use a small fixture file instead of the real 2MB OCR book to keep the test fast.
    fixture = tmp_path / "fixture-book.txt"
    fixture.write_text(
        "# OCR text extract: Fixture Book\n\n"
        "Some provenance note.\n"
        "\n---\n"
        "## Scanned page 001\n\n"
        "This is a clean English paragraph about pregnancy nutrition. " * 20
        + "\n\n## Scanned page 002\n\nAnother clean paragraph here. " * 20,
        encoding="utf-8",
    )
    monkeypatch.setattr(ingest_module, "BOOK_PATH", fixture)

    with SessionLocal() as db:
        ingest_module.ingest_book(db, api_key="fake-key", dry_run=False)

        sources = db.query(KnowledgeSource).filter_by(name="prasuti-tantra-premvati-tiwari").all()
        assert len(sources) == 1
        assert sources[0].review_status == "pending"

        documents = db.query(KnowledgeDocument).filter_by(source_id=sources[0].id).all()
        assert len(documents) == 1
        assert documents[0].review_status == "pending"
        assert documents[0].active is False

        chunks = db.query(KnowledgeChunk).filter_by(document_id=documents[0].id).all()
        assert len(chunks) > 0
        assert all(c.embedding == [0.1, 0.2, 0.3] for c in chunks)
        assert all("ocr_quality" in c.extra_metadata for c in chunks)


def test_book_ingestion_is_idempotent(client, tmp_path, monkeypatch) -> None:
    fixture = tmp_path / "fixture-book.txt"
    fixture.write_text("# note\n\n---\n\nSome content. " * 30, encoding="utf-8")
    monkeypatch.setattr(ingest_module, "BOOK_PATH", fixture)

    with SessionLocal() as db:
        ingest_module.ingest_book(db, api_key="fake-key", dry_run=False)
        ingest_module.ingest_book(db, api_key="fake-key", dry_run=False)
        assert db.query(KnowledgeSource).filter_by(name="prasuti-tantra-premvati-tiwari").count() == 1
