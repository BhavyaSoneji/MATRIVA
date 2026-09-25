"""One-time ingestion of the project's real curated knowledge into the live
SQL knowledge base -- not the eval-only RAG-core pgvector path, the actual
tables `/chat`, `/recommendations`, and `/knowledge/search` read from.

Ingests:
  - knowledge/ayurveda/Prasuti-Tantra-OCR.txt (real classical Ayurveda text,
    raw Tesseract OCR -- the file's own header says "NOT clinically or
    editorially reviewed" and that Devanagari/Sanskrit portions contain
    recognition errors)
  - knowledge/seed/seed.yaml (8 real curated documents: FOGSI ANC schedule,
    2 Garbhini Paricharya entries, 5 IFCT food nutrient profiles)

Safety policy (deliberate, not an oversight): everything this script inserts
gets review_status="pending" -- never "approved". The retrieval gate
(app/rag/retrieval.py's retrieve_chunks_scored) only serves APPROVED
source+document pairs to chat/recommendations/search. This matches both the
book's own disclaimer and this project's stated principle that
traditional/unreviewed content must not be presented as vetted (see
Master Prompt.txt, docs/COMPLIANCE.md). A real reviewer approves via the
existing admin API (POST /admin/documents/{id}/approve) -- this script does
not, and must not, bypass that gate itself.

Each chunk of the OCR book also gets a real per-chunk OCR-quality signal
(ascii_ratio, alpha_word_ratio) in extra_metadata so a reviewer can triage
by quality instead of reading 900+ chunks in document order. Nothing is
silently dropped for being low-quality -- that would misrepresent how much
of the book was actually processed.

Usage:
    python scripts/ingest_real_knowledge.py [--book-only | --seed-only] [--dry-run]

Idempotent: re-running skips any source that already exists (matched by a
deterministic `name`), so it's safe to run again after a partial failure.
"""

from __future__ import annotations

import argparse
import functools
import re
import sys
import time
from pathlib import Path

import yaml

# This script is meant to be watched while it runs (a full book can take a
# while); rebind print to always flush so progress is visible immediately
# even when stdout is redirected to a file, instead of sitting in a buffer
# until the process exits.
print = functools.partial(print, flush=True)

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
_INGESTION_DIR = _REPO_ROOT / "ingestion"
for path in (_BACKEND_DIR, _INGESTION_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from google.api_core.exceptions import ResourceExhausted
from pipelines.chunker import _group_blocks
from pipelines.parser import clean_text
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import (
    AyurvedicSource,
    EvidenceMetadata,
    FoodItem,
    Guideline,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
    ReviewStatus,
    SafetyStatus,
    User,
    UserRole,
)
from app.rag.embeddings import embed_text

BOOK_PATH = _REPO_ROOT / "knowledge" / "ayurveda" / "Prasuti-Tantra-OCR.txt"
SEED_YAML_PATH = _REPO_ROOT / "knowledge" / "seed" / "seed.yaml"

# Maps the RAG-core schema's finer-grained pending reason onto the SQL
# layer's single ReviewStatus.PENDING -- both still block retrieve_chunks_scored
# identically; the reason is preserved in extra_metadata for reviewers.
_PENDING_REASON = {
    "PENDING_SOURCE_VERIFICATION": "source_verification",
    "PENDING_CLINICAL_REVIEW": "clinical_review",
}

# seed.yaml uses the RAG-core schema's SourceType vocabulary
# (app/schemas/knowledge.py), which is finer-grained than the SQL/API
# layer's SourceType (app/models/entities.py). Map onto the closest SQL value.
_SOURCE_TYPE_MAP = {
    "medical_guideline": "professional_society",
    "ayurvedic_classical_source": "traditional",
    "nutrition_reference": "government",
}

_EMBED_RETRIES = 2
_EMBED_BACKOFF_SECONDS = 3

# Set once a quota-exhaustion error is seen -- retrying a 429 ResourceExhausted
# is pointless (it will not recover mid-run) and previously wasted ~30s per
# chunk on backoff before finally giving up, stretching a several-minute job
# into 30+ minutes for nothing. Once tripped, every remaining chunk in this
# process skips straight to "no embedding" without calling the API again.
_quota_exhausted = False


def _get_or_create_ingestion_user(db: Session) -> User:
    user = db.execute(select(User).where(User.email == "ingestion-bot@matriva.internal")).scalar_one_or_none()
    if user:
        return user
    user = User(
        email="ingestion-bot@matriva.internal",
        password_hash="!disabled",
        full_name="Knowledge Ingestion (automated)",
        role=UserRole.ADMIN.value,
        is_active=False,
    )
    db.add(user)
    db.flush()
    return user


def _check_embedding_quota(api_key: str) -> bool:
    """One cheap upfront call so a dead quota is discovered in ~1 call
    instead of after every chunk retries and fails identically."""
    try:
        embed_text("quota check", api_key=api_key)
        return True
    except ResourceExhausted as exc:
        print(f"[warn] embedding quota already exhausted, proceeding without embeddings: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] embedding quota check failed ({exc}); will still try per-chunk")
        return True


def _embed_with_retry(text: str, api_key: str) -> list[float] | None:
    global _quota_exhausted
    if _quota_exhausted:
        return None
    for attempt in range(1, _EMBED_RETRIES + 1):
        try:
            return embed_text(text, api_key=api_key)
        except ResourceExhausted as exc:
            print(f"    [warn] embedding quota exhausted mid-run, disabling embeddings for the rest of this run: {exc}")
            _quota_exhausted = True
            return None
        except Exception as exc:  # noqa: BLE001
            if attempt == _EMBED_RETRIES:
                print(f"    [warn] embedding failed after {attempt} attempts: {exc}")
                return None
            time.sleep(_EMBED_BACKOFF_SECONDS * attempt)
    return None


def _quality_signal(text: str) -> dict[str, float]:
    words = re.findall(r"[A-Za-z]{2,}", text)
    ascii_ratio = sum(c.isascii() for c in text) / max(len(text), 1)
    alpha_word_ratio = len(words) / max(len(text.split()), 1)
    return {"ascii_ratio": round(ascii_ratio, 3), "alpha_word_ratio": round(alpha_word_ratio, 3)}


def ingest_book(db: Session, *, api_key: str | None, dry_run: bool) -> None:
    print(f"[book] reading {BOOK_PATH}")
    raw = BOOK_PATH.read_text(encoding="utf-8")

    existing = db.execute(
        select(KnowledgeSource).where(KnowledgeSource.name == "prasuti-tantra-premvati-tiwari")
    ).scalar_one_or_none()
    if existing:
        print("[book] already ingested (source 'prasuti-tantra-premvati-tiwari' exists) -- skipping")
        return

    # Strip this repo's own OCR-provenance header (metadata, not book content)
    # and the per-page "## Scanned page NNN" / "---" markers the OCR export adds.
    header_end = raw.find("\n---\n")
    body = raw[header_end + len("\n---\n") :] if header_end != -1 else raw
    body = re.sub(r"^## Scanned page \d+\s*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"^---\s*$", "", body, flags=re.MULTILINE)
    cleaned = clean_text(body)

    blocks = [b for b in cleaned.split("\n\n") if b.strip()]
    groups = _group_blocks(blocks, 300, 700)
    print(f"[book] parsed into {len(groups)} chunks")

    if dry_run:
        print("[book] --dry-run: not writing to the database")
        return

    ingestion_user = _get_or_create_ingestion_user(db)

    source = KnowledgeSource(
        name="prasuti-tantra-premvati-tiwari",
        title="Prasuti Tantra evam Stri Roga (Vol. 1: Prasuti Tantra)",
        source_type="traditional",
        authority="Dr. Premvati Tiwari; Chaukhambha Orientalia, Varanasi",
        jurisdiction="India",
        topic="prasuti_tantra",
        review_status=ReviewStatus.PENDING.value,
        evidence_level="traditional",
        description=(
            "Real classical Ayurveda textbook, ingested from a raw Tesseract OCR scan "
            "(see knowledge/ayurveda/Prasuti-Tantra-OCR.txt). The OCR is genuinely rough: "
            "even chunks that score well on the ascii/alpha-word heuristics below still "
            "contain broken word-wrapping from column layout and stray Devanagari "
            "characters. NOT reviewed for clinical or translation accuracy. Do not "
            "approve individual chunks without checking them against the original text."
        ),
        extra_metadata={"real_data": True, "ocr_source": True, "pending_reason": "clinical_review"},
    )
    db.add(source)
    db.flush()

    document = KnowledgeDocument(
        source_id=source.id,
        title="Prasuti Tantra (OCR)",
        domain="ayurveda",
        subdomain="prasuti_tantra",
        language="en",
        region="IN",
        pregnancy_stage=None,  # applies to all stages; see stage-filter note in _ingest_seed_document
        review_status=ReviewStatus.PENDING.value,
        index_status="indexed",
        content_hash=str(hash(cleaned)),
        file_name="Prasuti-Tantra-OCR.txt",
        mime_type="text/plain",
        raw_content=raw.encode("utf-8"),
        active=False,
        created_by=ingestion_user.id,
    )
    db.add(document)
    db.flush()

    high_quality = 0
    embedded = 0
    for index, group in enumerate(groups):
        signal = _quality_signal(group)
        if signal["ascii_ratio"] > 0.9 and signal["alpha_word_ratio"] > 0.75:
            high_quality += 1
        embedding = None
        if api_key:
            embedding = _embed_with_retry(group, api_key)
            if embedding:
                embedded += 1
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                source_id=source.id,
                chunk_index=index,
                content=group,
                embedding=embedding,
                extra_metadata={"ocr_quality": signal},
            )
        )
        if (index + 1) % 100 == 0:
            db.flush()
            print(f"[book] processed {index + 1}/{len(groups)} chunks ({embedded} embedded)")

    db.add(
        EvidenceMetadata(
            source_id=source.id,
            evidence_level="traditional",
            evidence_label="Real classical text, OCR quality unverified",
            review_status=ReviewStatus.PENDING.value,
            notes="Raw Tesseract OCR; needs a qualified reviewer before any chunk is approved.",
        )
    )
    db.commit()
    print(
        f"[book] done: {len(groups)} chunks stored, {high_quality} scored high-quality by "
        f"heuristic, {embedded} embedded. review_status=pending (not visible to chat yet)."
    )


def _ingest_seed_document(db: Session, entry: dict, *, api_key: str | None, ingestion_user: User) -> None:
    name = entry["document_id"]
    existing = db.execute(select(KnowledgeSource).where(KnowledgeSource.name == name)).scalar_one_or_none()
    if existing:
        print(f"[seed] {name} already ingested -- skipping")
        return

    pending_reason = _PENDING_REASON.get(entry["review_status"], "source_verification")
    # retrieve_chunks_scored's stage filter treats NULL as "applies to every
    # stage" -- the literal string "all" would instead exclude this document
    # from every stage-specific query, the opposite of what seed.yaml means.
    pregnancy_stage = entry.get("pregnancy_stage")
    if pregnancy_stage == "all":
        pregnancy_stage = None
    source = KnowledgeSource(
        name=name,
        title=entry["title"],
        source_type=_SOURCE_TYPE_MAP.get(entry["source_type"], "internal"),
        jurisdiction=entry.get("region") or "India",
        topic=entry.get("topic"),
        version=entry.get("version"),
        review_status=ReviewStatus.PENDING.value,
        evidence_level=entry["evidence_level"].lower(),
        description=f"Real curated entry from knowledge/seed/seed.yaml ({entry['document_id']}).",
        extra_metadata={"real_data": True, "pending_reason": pending_reason},
    )
    db.add(source)
    db.flush()

    content = entry["content"].strip()
    document = KnowledgeDocument(
        source_id=source.id,
        title=entry["title"],
        domain=entry["domain"].lower(),
        subdomain=entry.get("subdomain"),
        language=entry.get("language", "en"),
        region=entry.get("region"),
        pregnancy_stage=pregnancy_stage,
        review_status=ReviewStatus.PENDING.value,
        index_status="indexed",
        content_hash=str(hash(content)),
        file_name=f"{name}.txt",
        mime_type="text/plain",
        raw_content=content.encode("utf-8"),
        active=False,
        created_by=ingestion_user.id,
    )
    db.add(document)
    db.flush()

    embedding = _embed_with_retry(content, api_key) if api_key else None
    db.add(
        KnowledgeChunk(
            document_id=document.id,
            source_id=source.id,
            chunk_index=0,
            content=content,
            embedding=embedding,
            extra_metadata={"real_data": True},
        )
    )

    db.add(
        EvidenceMetadata(
            source_id=source.id,
            evidence_level=entry["evidence_level"].lower(),
            evidence_label=f"Real curated entry, pending {pending_reason.replace('_', ' ')}",
            review_status=ReviewStatus.PENDING.value,
            notes="Loaded from knowledge/seed/seed.yaml.",
        )
    )

    if entry["domain"] == "MODERN_MEDICAL" and "anc" in entry.get("topic", ""):
        db.add(
            Guideline(
                source_id=source.id,
                authority=entry.get("source_id", "FOGSI"),
                jurisdiction=entry.get("region") or "India",
                status="pending",
                scope_notes="Real FOGSI/WHO ANC schedule excerpt; verify against the current published guideline before approval.",
            )
        )

    if entry["domain"] == "AYURVEDA":
        db.add(
            AyurvedicSource(
                source_id=source.id,
                book="Charaka Samhita (Sharirasthana, Garbhini Paricharya)",
                chapter="8",
                translation=content,
                interpretation="Traditional antenatal regimen principle -- requires Clinical Lead sign-off before presentation as vetted guidance.",
                traditional_context="Garbhini Paricharya (month-wise antenatal regimen)",
                evidence_label="traditional",
                provenance={"source_yaml": "knowledge/seed/seed.yaml", "document_id": name},
            )
        )

    if entry["domain"] == "NUTRITION":
        db.add(
            FoodItem(
                name=entry["title"].split(" - ")[0].strip(),
                region=entry.get("region") or "India",
                pregnancy_context=content,
                evidence_status=entry["evidence_level"].lower(),
                safety_status=SafetyStatus.SAFE_GENERAL.value,
                source_ids=[source.id],
                # Inactive until the source itself is approved -- FoodItem has
                # no review-status gate of its own (see /knowledge/food), so
                # leaving this active=True would bypass the pending-review
                # policy for nutrition data specifically.
                active=False,
            )
        )

    db.commit()
    print(f"[seed] ingested {name} (embedded={'yes' if embedding else 'no'})")


def ingest_seed_yaml(db: Session, *, api_key: str | None, dry_run: bool) -> None:
    entries = yaml.safe_load(SEED_YAML_PATH.read_text(encoding="utf-8"))
    print(f"[seed] {len(entries)} documents in {SEED_YAML_PATH}")
    if dry_run:
        print("[seed] --dry-run: not writing to the database")
        return
    ingestion_user = _get_or_create_ingestion_user(db)
    for entry in entries:
        _ingest_seed_document(db, entry, api_key=api_key, ingestion_user=ingestion_user)


def main() -> None:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-only", action="store_true")
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Parse/chunk only, don't write to the database")
    args = parser.parse_args()

    api_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[warn] no EMBEDDING_API_KEY/GEMINI_API_KEY set -- chunks will be stored without embeddings")

    with SessionLocal() as db:
        if not args.seed_only:
            ingest_book(db, api_key=api_key, dry_run=args.dry_run)
        if not args.book_only:
            ingest_seed_yaml(db, api_key=api_key, dry_run=args.dry_run)

    print("\nDone. Everything above is review_status=pending -- approve via POST /admin/documents/{id}/approve to make it live.")


if __name__ == "__main__":
    main()
