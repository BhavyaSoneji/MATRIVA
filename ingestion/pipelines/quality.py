"""Metadata enrichment + document quality checks (issue #4).

Section 38 (DOCUMENT QUALITY CONTROL): before indexing, check source exists,
source identity, document readability, duplicate content, metadata
completeness, domain, evidence status, pregnancy relevance, safety relevance.
Rejected documents must not enter the active retrieval corpus.

Section 39 (DUPLICATE DETECTION): document hash + semantic similarity.

Semantic similarity here is a lightweight, dependency-free stand-in
(difflib SequenceMatcher over normalized text) -- swap for real embedding
cosine similarity once #5 (Gemini embeddings + pgvector) lands. Same
pattern as Sprint 0's seed_qa.py using keyword overlap ahead of #6.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import StrEnum
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.safety.pre_check import RED_FLAGS  # noqa: E402
from app.schemas.knowledge import KnowledgeDocument  # noqa: E402

MIN_CONTENT_WORDS = 20
DUPLICATE_SIMILARITY_THRESHOLD = 0.85


class Severity(StrEnum):
    FAIL = "FAIL"  # blocks ingestion
    WARN = "WARN"  # passes, but flagged for human review


@dataclass
class CheckResult:
    name: str
    severity: Severity
    passed: bool
    message: str


@dataclass
class QualityReport:
    document_id: str
    accepted: bool
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == Severity.FAIL]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == Severity.WARN]


def normalize_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def content_hash(content: str) -> str:
    return hashlib.sha256(normalize_for_hash(content).encode("utf-8")).hexdigest()


def semantic_similarity(a: str, b: str) -> float:
    """Lightweight stand-in for embedding cosine similarity (see #5)."""
    return SequenceMatcher(None, normalize_for_hash(a), normalize_for_hash(b)).ratio()


@dataclass
class DuplicateMatch:
    existing_document_id: str
    match_type: str  # "exact_hash" | "semantic"
    similarity: float


def find_duplicates(
    document: KnowledgeDocument,
    corpus: list[KnowledgeDocument],
    *,
    similarity_threshold: float = DUPLICATE_SIMILARITY_THRESHOLD,
) -> list[DuplicateMatch]:
    matches: list[DuplicateMatch] = []
    target_hash = content_hash(document.content)
    for existing in corpus:
        if existing.document_id == document.document_id:
            continue
        if content_hash(existing.content) == target_hash:
            matches.append(DuplicateMatch(existing.document_id, "exact_hash", 1.0))
            continue
        similarity = semantic_similarity(document.content, existing.content)
        if similarity >= similarity_threshold:
            matches.append(DuplicateMatch(existing.document_id, "semantic", similarity))
    return matches


def _check_source_exists(document: KnowledgeDocument) -> CheckResult:
    ok = bool(document.source_id and document.source_id.strip())
    return CheckResult(
        "source_exists", Severity.FAIL, ok,
        "source_id present" if ok else "source_id missing or empty",
    )


def _check_source_identity(document: KnowledgeDocument) -> CheckResult:
    ok = document.source_type is not None
    return CheckResult(
        "source_identity", Severity.FAIL, ok,
        "source_type set" if ok else "source_type missing",
    )


def _check_readability(document: KnowledgeDocument) -> CheckResult:
    word_count = len(document.content.split())
    ok = word_count >= MIN_CONTENT_WORDS
    return CheckResult(
        "document_readability", Severity.FAIL, ok,
        f"{word_count} words" if ok else f"only {word_count} words (min {MIN_CONTENT_WORDS})",
    )


def _check_metadata_completeness(document: KnowledgeDocument) -> CheckResult:
    missing = [
        field_name
        for field_name in ("document_id", "title", "domain", "source_id", "source_type")
        if not getattr(document, field_name)
    ]
    ok = not missing
    return CheckResult(
        "metadata_completeness", Severity.FAIL, ok,
        "all required fields present" if ok else f"missing: {', '.join(missing)}",
    )


def _check_domain(document: KnowledgeDocument) -> CheckResult:
    ok = document.domain is not None
    return CheckResult("domain", Severity.FAIL, ok, "domain set" if ok else "domain missing")


def _check_evidence_status(document: KnowledgeDocument) -> CheckResult:
    ok = document.evidence_level is not None
    return CheckResult(
        "evidence_status", Severity.FAIL, ok,
        "evidence_level set" if ok else "evidence_level missing",
    )


def _check_pregnancy_relevance(document: KnowledgeDocument) -> CheckResult:
    # Soft check: many documents are legitimately stage-agnostic (e.g. general
    # nutrient facts). Missing pregnancy_stage is a WARN for reviewer
    # attention, not an automatic reject.
    ok = bool(document.pregnancy_stage)
    return CheckResult(
        "pregnancy_relevance", Severity.WARN, ok,
        "pregnancy_stage set" if ok else "pregnancy_stage not set -- confirm this is intentional",
    )


def _check_safety_relevance(document: KnowledgeDocument) -> CheckResult:
    # If content mentions an obstetric danger sign (#67's red-flag list) but
    # isn't tagged, flag it -- a reviewer should confirm the safety_tags.
    normalized = normalize_for_hash(document.content)
    matched = [
        category
        for category, phrases in RED_FLAGS.items()
        if any(phrase in normalized for phrase in phrases)
    ]
    if not matched:
        return CheckResult("safety_relevance", Severity.WARN, True, "no danger-sign terms found")
    ok = bool(document.safety_tags)
    return CheckResult(
        "safety_relevance", Severity.WARN, ok,
        f"tagged (safety_tags={document.safety_tags})" if ok
        else f"mentions danger-sign terms {matched} but safety_tags is empty -- confirm tagging",
    )


def check_document_quality(
    document: KnowledgeDocument, corpus: list[KnowledgeDocument] | None = None
) -> QualityReport:
    """Run all Section 38 checks (+ Section 39 duplicate detection) on a document.

    `corpus` is the existing accepted-document set to check duplicates against.
    A document is rejected (never enters the active retrieval corpus) if any
    FAIL-severity check fails; WARN-severity failures pass through but should
    surface for human review.
    """
    corpus = corpus or []
    checks = [
        _check_source_exists(document),
        _check_source_identity(document),
        _check_readability(document),
        _check_metadata_completeness(document),
        _check_domain(document),
        _check_evidence_status(document),
        _check_pregnancy_relevance(document),
        _check_safety_relevance(document),
    ]

    duplicates = find_duplicates(document, corpus)
    dup_ok = not duplicates
    checks.append(
        CheckResult(
            "duplicate_content", Severity.FAIL, dup_ok,
            "no duplicates found" if dup_ok
            else f"duplicate of {[d.existing_document_id for d in duplicates]}",
        )
    )

    accepted = not any(not c.passed and c.severity == Severity.FAIL for c in checks)
    return QualityReport(document_id=document.document_id, accepted=accepted, checks=checks)
