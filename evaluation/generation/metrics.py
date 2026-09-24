"""Generation evaluation metrics (issue #17, Master Prompt Section 41).

Automates what can reasonably be automated (groundedness, citation
correctness, a relevance proxy, a completeness proxy) by reusing #10/#13's
existing safety/evidence modules -- rather than reimplementing citation or
claim checking here. Clarity and final quality judgment are explicitly left
to the human-review checklist (`human_review_checklist.md`), per Section
41's "use human review for final quality assessment" -- clarity is not
something a rule-based script can meaningfully score.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.evidence.citation_validation import (
    validate_citations_against_packet,
)
from app.rag.context_packet import ContextPacket
from app.rag.keyword_search import keyword_overlap_score, tokenize
from app.safety.post_check import (
    detect_source_inconsistency,
    detect_unsupported_medical_claims,
)

MIN_COMPLETE_WORD_COUNT = 20


@dataclass
class CitationCorrectnessResult:
    verified_count: int
    unverifiable_count: int
    is_clean: bool


def citation_correctness(response: str, context_packet: ContextPacket) -> CitationCorrectnessResult:
    result = validate_citations_against_packet(response, context_packet)
    return CitationCorrectnessResult(
        verified_count=len(result.verified_citation_ids),
        unverifiable_count=len(result.unverifiable_citation_ids),
        is_clean=result.is_clean,
    )


@dataclass
class GroundednessResult:
    grounded: bool
    unsupported_claim_phrases: list[str]
    source_inconsistent: bool


def groundedness_check(response: str, context_packet: ContextPacket) -> GroundednessResult:
    unsupported = detect_unsupported_medical_claims(response, context_packet)
    inconsistent = detect_source_inconsistency(response, context_packet)
    return GroundednessResult(
        grounded=not unsupported and not inconsistent,
        unsupported_claim_phrases=unsupported,
        source_inconsistent=inconsistent,
    )


def answer_relevance(query: str, response: str) -> float:
    """Keyword-overlap proxy for relevance -- crude, but consistent with the
    lightweight stand-ins used elsewhere in this project (#6, #4) ahead of a
    real semantic similarity measure. Fraction of query terms echoed
    (directly or via shared vocabulary) in the response."""
    query_terms = tokenize(query)
    if not query_terms:
        return 0.0
    overlap = keyword_overlap_score(query, response)
    return min(overlap / len(query_terms), 1.0)


@dataclass
class CompletenessResult:
    word_count: int
    has_citation: bool
    likely_complete: bool


def completeness_check(
    response: str, context_packet: ContextPacket, min_words: int = MIN_COMPLETE_WORD_COUNT
) -> CompletenessResult:
    """Proxy only: a response citing evidence and not implausibly short is
    "likely complete." Does not verify the answer actually addresses every
    part of a multi-part question -- that needs human review."""
    word_count = len(response.split())
    has_citation = citation_correctness(response, context_packet).verified_count > 0
    likely_complete = word_count >= min_words and (
        has_citation or not context_packet.retrieved_sources
    )
    return CompletenessResult(
        word_count=word_count, has_citation=has_citation, likely_complete=likely_complete
    )
