import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evidence.citation_validation import (
    validate_citations,
    validate_citations_against_packet,
)
from app.rag.context_packet import build_context_packet
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk


def test_clean_answer_with_no_citations_is_unchanged() -> None:
    result = validate_citations("This is a plain answer with no citations.", {"chunk-1"})
    assert result.is_clean
    assert result.cleaned_answer == "This is a plain answer with no citations."


def test_valid_citation_passes_through_unchanged() -> None:
    result = validate_citations("Eat iron-rich foods [chunk-1].", {"chunk-1"})
    assert result.is_clean
    assert result.verified_citation_ids == ["chunk-1"]
    assert "[chunk-1]" in result.cleaned_answer


def test_unverifiable_citation_is_stripped_and_flagged() -> None:
    result = validate_citations("Some claim [fake-chunk-99].", {"chunk-1"})
    assert not result.is_clean
    assert result.unverifiable_citation_ids == ["fake-chunk-99"]
    assert "[fake-chunk-99]" not in result.cleaned_answer
    assert "citation removed" in result.cleaned_answer


def test_multiple_citations_mixed_valid_and_invalid() -> None:
    result = validate_citations("See [chunk-1] and also [chunk-99].", {"chunk-1"})
    assert result.verified_citation_ids == ["chunk-1"]
    assert result.unverifiable_citation_ids == ["chunk-99"]
    assert "[chunk-1]" in result.cleaned_answer
    assert "[chunk-99]" not in result.cleaned_answer


def test_invented_url_is_stripped_and_flagged() -> None:
    result = validate_citations("Read more at https://example.com/fake-source.", {"chunk-1"})
    assert not result.is_clean
    assert result.fabricated_urls == ["https://example.com/fake-source."]
    assert "https://" not in result.cleaned_answer


def test_page_reference_is_stripped_and_flagged() -> None:
    result = validate_citations("See page 42 for details.", {"chunk-1"})
    assert not result.is_clean
    assert len(result.fabricated_page_references) == 1
    assert "page 42" not in result.cleaned_answer.lower()


def test_page_reference_p_dot_form_is_also_caught() -> None:
    result = validate_citations("Reference p. 12 confirms this.", {"chunk-1"})
    assert not result.is_clean
    assert len(result.fabricated_page_references) == 1


def test_validate_against_packet_accepts_chunk_document_and_source_ids() -> None:
    chunk = KnowledgeChunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        source_id="fogsi-gcpr",
        domain=Domain.MODERN_MEDICAL,
        evidence_level=EvidenceLevel.SUPPORTED,
        content="ANC schedule content",
        chunk_index=0,
    )
    packet = build_context_packet("question", [(chunk, 1.0)], safety_result={})

    for valid_ref in ("chunk-1", "doc-1", "fogsi-gcpr"):
        result = validate_citations_against_packet(f"Per [{valid_ref}].", packet)
        assert result.is_clean, f"{valid_ref} should validate"

    result = validate_citations_against_packet("Per [nonexistent-id].", packet)
    assert not result.is_clean
