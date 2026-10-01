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
import yaml

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


def _count(path) -> int:
    return len(yaml.safe_load(path.read_text(encoding="utf-8")))


# seed.yaml (8: FOGSI ANC, 2 Garbhini Paricharya, 5 IFCT foods) + guidelines.yaml + foods.yaml
EXPECTED_SEED_DOCS = 8 + _count(ingest_module.GUIDELINES_YAML_PATH) + _count(ingest_module.FOODS_YAML_PATH)
EXPECTED_FOOD_ITEMS = 5 + _count(ingest_module.FOODS_YAML_PATH)


@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_module, "embed_text", lambda text, api_key=None: [0.1, 0.2, 0.3])


def test_seed_yaml_ingests_all_documents_as_pending(client) -> None:
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)

        sources = db.query(KnowledgeSource).all()
        assert len(sources) == EXPECTED_SEED_DOCS
        assert all(s.review_status == "pending" for s in sources)

        documents = db.query(KnowledgeDocument).all()
        assert len(documents) == EXPECTED_SEED_DOCS
        assert all(d.review_status == "pending" and d.active is False for d in documents)

        chunks = db.query(KnowledgeChunk).all()
        assert len(chunks) == EXPECTED_SEED_DOCS
        assert all(c.embedding == [0.1, 0.2, 0.3] for c in chunks)


def test_seed_yaml_creates_structured_side_records(client) -> None:
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)

        assert db.query(Guideline).count() == 1
        assert db.query(AyurvedicSource).count() == 2

        food_items = db.query(FoodItem).all()
        assert len(food_items) == EXPECTED_FOOD_ITEMS
        # FoodItem has no review-status gate of its own (see /knowledge/food) --
        # must stay inactive until the source is approved, or nutrition data
        # would bypass the pending-review policy entirely.
        assert all(item.active is False for item in food_items)


def test_seed_yaml_ingestion_is_idempotent(client) -> None:
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)
        assert db.query(KnowledgeSource).count() == EXPECTED_SEED_DOCS
        assert db.query(KnowledgeDocument).count() == EXPECTED_SEED_DOCS


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


def test_guideline_entries_are_pending_with_source_urls_and_safe_topics(client) -> None:
    """Paraphrased WHO/NHS/MoHFW entries must stay pending, cite a primary URL, and not
    trip the 'anc' substring check that auto-creates a Guideline row."""
    entries = yaml.safe_load(ingest_module.GUIDELINES_YAML_PATH.read_text(encoding="utf-8"))
    assert len(entries) >= 12
    for entry in entries:
        assert entry["review_status"] == "PENDING_SOURCE_VERIFICATION"
        assert entry["url"].startswith("https://")
        assert "anc" not in entry["topic"]
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake-key", dry_run=False)
        assert db.query(Guideline).count() == 1  # still only the FOGSI ANC entry
        who = db.query(KnowledgeSource).filter(KnowledgeSource.name == "guide-who-iron-folate-001").one()
        assert who.url and who.authority == "World Health Organization"
        assert who.review_status == "pending"


def test_usda_food_entries_are_pending_cited_and_numeric(client) -> None:
    entries = yaml.safe_load(ingest_module.FOODS_YAML_PATH.read_text(encoding="utf-8"))
    assert len(entries) >= 60
    ids = [e["document_id"] for e in entries]
    assert len(ids) == len(set(ids))
    for entry in entries:
        assert entry["review_status"] == "PENDING_SOURCE_VERIFICATION"
        assert entry["domain"] == "NUTRITION"
        assert entry["url"].startswith("https://fdc.nal.usda.gov/")
        assert "anc" not in entry["topic"]
        # the exact USDA record and real per-100 g numbers are in the text
        assert "per 100 g" in entry["content"] and "SR Legacy record" in entry["content"]
        assert "protein" in entry["content"] and "iron" in entry["content"]
    liver = next(e for e in entries if "liver" in e["title"].lower())
    assert "avoiding liver" in liver["content"] and "avoid_in_pregnancy" in liver["safety_tags"]


_ENGLISH_PAGE = (
    "The pregnant woman should take milk and ghee regularly because it nourishes the mother and supports "
    "the growth of the fetus during the later months of pregnancy according to the classical text. "
)


def test_book_sections_are_pending_paged_and_scored(client, tmp_path, monkeypatch) -> None:
    fixture = tmp_path / "book.txt"
    pages = "".join(
        f"\n---\n## Scanned page {n:03d}\n\nदेवनागरी पाठ जो हटाया जाएगा\n\n{_ENGLISH_PAGE * 3}\n" for n in range(1, 31)
    )
    fixture.write_text("# header\n" + pages, encoding="utf-8")
    monkeypatch.setattr(ingest_module, "BOOK_PATH", fixture)

    with SessionLocal() as db:
        ingest_module.ingest_book_sections(db, dry_run=False)
        source = db.query(KnowledgeSource).filter_by(name=ingest_module.BOOK_SECTIONS_SOURCE).one()
        assert source.review_status == "pending" and source.evidence_level == "traditional"
        docs = db.query(KnowledgeDocument).filter_by(source_id=source.id).all()
        assert len(docs) == 3  # 30 pages / 12 per section
        assert all(d.review_status == "pending" and d.active is False and d.domain == "ayurveda" for d in docs)
        chunks = db.query(KnowledgeChunk).filter_by(source_id=source.id).all()
        assert chunks and all("scanned p" in c.extra_metadata["page_or_section"] for c in chunks)
        assert all("readability" in c.extra_metadata["ocr_quality"] for c in chunks)
        assert not any("देवनागरी" in c.content for c in chunks)  # Devanagari OCR is excluded
        ingest_module.ingest_book_sections(db, dry_run=False)  # idempotent
        assert db.query(KnowledgeDocument).filter_by(source_id=source.id).count() == 3


def _chapter_book(pages: int = 12) -> str:
    """A tiny book in the shape of the real scan: two chapters headed `अध्याय / CHAPTER / (TITLE)`."""
    out = ["# header\n"]
    for n in range(1, 27 + pages):
        head = ""
        if n == 27:
            head = "अध्याय १\nCHAPTER I\nप्रथम शीर्षक\n(ANATOMY OF THE WOMAN)\n"
        if n == 27 + pages // 2:
            head = "अध्याय २\nCHAPTER II\nद्वितीय शीर्षक\n(MILK AND REGIMEN FOR PREGNANCY)\n"
        out.append(f"\n---\n## Scanned page {n:03d}\n\n{head}देवनागरी मूल पाठ यहाँ हिन्दी में लिखा है जो मूल है\n\n{_ENGLISH_PAGE * 3 if n >= 27 else ''}\n")
    return "".join(out)


def test_book_chapters_ingest_with_structure_provenance_and_pending(client, tmp_path, monkeypatch) -> None:
    fixture = tmp_path / "book.txt"
    fixture.write_text(_chapter_book(), encoding="utf-8")
    monkeypatch.setattr(ingest_module, "BOOK_PATH", fixture)
    with SessionLocal() as db:
        ingest_module.ingest_book_chapters(db, dry_run=False)
        source = db.query(KnowledgeSource).filter_by(name=ingest_module.BOOK_CHAPTERS_SOURCE).one()
        assert source.review_status == "pending" and source.evidence_level == "traditional"
        docs = db.query(KnowledgeDocument).filter_by(source_id=source.id).order_by(KnowledgeDocument.title).all()
        assert [d.title for d in docs] == [
            "Prasuti Tantra - Chapter 1: Anatomy Of The Woman",
            "Prasuti Tantra - Chapter 2: Milk And Regimen For Pregnancy",
        ]
        assert all(d.review_status == "pending" and d.active is False for d in docs)
        chunks = db.query(KnowledgeChunk).filter_by(document_id=docs[1].id).all()
        meta = chunks[0].extra_metadata
        assert meta["chapter"] == 2 and meta["page_or_section"].startswith("Ch. 2")
        assert "scanned p" in meta["page_or_section"] and "readability" in meta["ocr_quality"]
        assert "देवनागरी" in meta["original_hi"]  # Hindi original kept as provenance...
        assert not any("देवनागरी" in c.content for c in chunks)  # ...but never searched or quoted
        ingest_module.ingest_book_chapters(db, dry_run=False)  # idempotent
        assert db.query(KnowledgeDocument).filter_by(source_id=source.id).count() == 2
        ingest_module.ingest_book_chapters(db, dry_run=False, replace=True)  # replace rebuilds, no duplicates
        assert db.query(KnowledgeSource).filter_by(name=ingest_module.BOOK_CHAPTERS_SOURCE).count() == 1
