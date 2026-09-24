import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.multi_domain import (
    detect_domains,
    multi_domain_retrieval_filter,
    requires_segmentation,
    validate_segmentation,
)
from app.schemas.knowledge import Domain


def test_detect_domains_finds_all_relevant_domains_for_section_31_example() -> None:
    query = (
        "I am vegetarian and in my second trimester. What Gujarati foods are "
        "relevant, and what does Ayurveda say about them?"
    )
    domains = detect_domains(query)
    assert Domain.NUTRITION in domains
    assert Domain.REGIONAL_CULTURAL in domains
    assert Domain.AYURVEDA in domains


def test_detect_domains_single_domain_query() -> None:
    domains = detect_domains("What yoga exercises are safe?")
    assert domains == [Domain.LIFESTYLE]


def test_detect_domains_no_match_returns_empty() -> None:
    assert detect_domains("What's the weather like today?") == []


def test_retrieval_filter_none_when_single_or_no_domain_detected() -> None:
    assert multi_domain_retrieval_filter("What yoga exercises are safe?") is None
    assert multi_domain_retrieval_filter("What's the weather like today?") is None


def test_retrieval_filter_returns_domains_when_genuinely_multi_domain() -> None:
    query = (
        "I am vegetarian and in my second trimester. What Gujarati foods are "
        "relevant, and what does Ayurveda say about them?"
    )
    result = multi_domain_retrieval_filter(query)
    assert result is not None
    assert Domain.AYURVEDA in result
    assert Domain.NUTRITION in result


def test_requires_segmentation_true_when_ayurveda_plus_other_domain() -> None:
    assert requires_segmentation(["AYURVEDA", "NUTRITION"]) is True


def test_requires_segmentation_false_when_ayurveda_only() -> None:
    assert requires_segmentation(["AYURVEDA"]) is False


def test_requires_segmentation_false_when_no_ayurveda() -> None:
    assert requires_segmentation(["NUTRITION", "REGIONAL_CULTURAL"]) is False


def test_requires_segmentation_false_when_empty() -> None:
    assert requires_segmentation([]) is False


def test_validate_segmentation_passes_when_all_sections_present() -> None:
    response = (
        "MODERN MEDICAL INFORMATION\n...\n\n"
        "TRADITIONAL/AYURVEDIC INFORMATION\n...\n\n"
        "EVIDENCE STATUS\n..."
    )
    result = validate_segmentation(response)
    assert result.is_segmented
    assert result.missing_sections == []


def test_validate_segmentation_flags_missing_sections() -> None:
    response = "Just a plain blended answer with no section headers at all."
    result = validate_segmentation(response)
    assert not result.is_segmented
    assert len(result.missing_sections) == 3
