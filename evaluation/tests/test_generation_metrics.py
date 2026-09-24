import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.context_packet import build_context_packet
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk

from generation.metrics import (
    answer_relevance,
    citation_correctness,
    completeness_check,
    groundedness_check,
)


def make_chunk(chunk_id: str, content: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        source_id="src-1",
        domain=Domain.NUTRITION,
        evidence_level=EvidenceLevel.SUPPORTED,
        content=content,
        chunk_index=0,
    )


def make_packet(chunks=None):
    chunks = chunks or []
    return build_context_packet(
        "What should I eat for iron during pregnancy?",
        [(c, 1.0) for c in chunks],
        safety_result={},
    )


# --- citation correctness -----------------------------------------------------

def test_citation_correctness_all_verified() -> None:
    chunk = make_chunk("c1", "spinach content")
    packet = make_packet([chunk])
    result = citation_correctness("Eat spinach [c1].", packet)
    assert result.is_clean
    assert result.verified_count == 1
    assert result.unverifiable_count == 0


def test_citation_correctness_unverifiable() -> None:
    packet = make_packet([make_chunk("c1", "spinach content")])
    result = citation_correctness("Eat spinach [fake-id].", packet)
    assert not result.is_clean
    assert result.unverifiable_count == 1


# --- groundedness ---------------------------------------------------------------

def test_groundedness_clean_response() -> None:
    chunk = make_chunk("c1", "spinach content")
    packet = make_packet([chunk])
    result = groundedness_check("Eat iron-rich spinach [c1].", packet)
    assert result.grounded


def test_groundedness_flags_unsupported_claims() -> None:
    packet = make_packet([])
    result = groundedness_check("You have anemia, definitely safe to ignore.", packet)
    assert not result.grounded
    assert result.unsupported_claim_phrases


def test_groundedness_flags_source_inconsistency() -> None:
    packet = make_packet([make_chunk("c1", "spinach content")])
    result = groundedness_check("Eat spinach [fake-id].", packet)
    assert not result.grounded
    assert result.source_inconsistent


# --- answer relevance -------------------------------------------------------------

def test_relevance_high_when_terms_overlap() -> None:
    score = answer_relevance(
        "What should I eat for iron during pregnancy?",
        "Eat iron-rich foods like spinach during pregnancy.",
    )
    assert score > 0.5


def test_relevance_low_when_unrelated() -> None:
    score = answer_relevance(
        "What should I eat for iron during pregnancy?",
        "The weather today is sunny with a light breeze.",
    )
    assert score < 0.3


def test_relevance_zero_for_empty_query_terms() -> None:
    assert answer_relevance("", "anything") == 0.0


# --- completeness -----------------------------------------------------------------

def test_completeness_likely_complete_with_citation_and_length() -> None:
    chunk = make_chunk("c1", "spinach content")
    packet = make_packet([chunk])
    long_response = " ".join(["word"] * 25) + " [c1]"
    result = completeness_check(long_response, packet)
    assert result.likely_complete
    assert result.has_citation


def test_completeness_flags_too_short() -> None:
    chunk = make_chunk("c1", "spinach content")
    packet = make_packet([chunk])
    result = completeness_check("Short answer [c1].", packet)
    assert not result.likely_complete


def test_completeness_flags_missing_citation_when_sources_available() -> None:
    chunk = make_chunk("c1", "spinach content")
    packet = make_packet([chunk])
    long_response = " ".join(["word"] * 25)
    result = completeness_check(long_response, packet)
    assert not result.likely_complete
    assert not result.has_citation


def test_completeness_ok_without_citation_when_no_sources_retrieved() -> None:
    packet = make_packet([])
    long_response = " ".join(["word"] * 25)
    result = completeness_check(long_response, packet)
    assert result.likely_complete
