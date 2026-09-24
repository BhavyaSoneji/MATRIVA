import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.schemas.knowledge import (  # noqa: E402
    AyurvedicProvenance,
    Domain,
    EvidenceLevel,
    KnowledgeDocument,
)

from pipelines.quality import (  # noqa: E402
    check_document_quality,
    content_hash,
    find_duplicates,
    semantic_similarity,
)

GOOD_CONTENT = (
    "Second trimester nutrition guidance for pregnant women includes iron-rich foods "
    "such as spinach and moong dal, along with adequate calcium from dairy sources "
    "like toned milk, to support fetal growth and maternal health throughout this stage."
)


def make_document(**overrides) -> KnowledgeDocument:
    defaults = dict(
        document_id="doc-1",
        title="Second Trimester Nutrition",
        content=GOOD_CONTENT,
        domain=Domain.NUTRITION,
        source_id="ifct-2017",
        source_type="nutrition_reference",
        evidence_level=EvidenceLevel.SUPPORTED,
        pregnancy_stage="second_trimester",
    )
    defaults.update(overrides)
    return KnowledgeDocument(**defaults)


def test_well_formed_document_is_accepted() -> None:
    report = check_document_quality(make_document())
    assert report.accepted
    assert not report.failures


def test_missing_source_id_is_rejected() -> None:
    doc = make_document()
    doc.source_id = ""
    report = check_document_quality(doc)
    assert not report.accepted
    assert any(c.name == "source_exists" for c in report.failures)


def test_short_content_fails_readability() -> None:
    report = check_document_quality(make_document(content="Too short."))
    assert not report.accepted
    assert any(c.name == "document_readability" for c in report.failures)


def test_exact_duplicate_is_rejected() -> None:
    original = make_document(document_id="doc-1")
    duplicate = make_document(document_id="doc-2")
    report = check_document_quality(duplicate, corpus=[original])
    assert not report.accepted
    dup_check = next(c for c in report.checks if c.name == "duplicate_content")
    assert not dup_check.passed
    assert "doc-1" in dup_check.message


def test_near_duplicate_detected_via_semantic_similarity() -> None:
    original = make_document(document_id="doc-1")
    near_dup = make_document(
        document_id="doc-2",
        content=GOOD_CONTENT + " Additional minor clarifying note appended at the end.",
    )
    matches = find_duplicates(near_dup, [original])
    assert len(matches) == 1
    assert matches[0].match_type == "semantic"
    assert matches[0].existing_document_id == "doc-1"


def test_distinct_documents_are_not_flagged_as_duplicates() -> None:
    original = make_document(document_id="doc-1")
    unrelated = make_document(
        document_id="doc-2",
        content="Garbhini Paricharya emphasizes calm routine and ghee-rich diet in later months.",
        domain=Domain.AYURVEDA,
        source_type="ayurvedic_classical_source",
        evidence_level=EvidenceLevel.TRADITIONAL,
        ayurvedic_provenance=AyurvedicProvenance(
            source="Charaka Samhita",
            book="Charaka Samhita",
            chapter="Sharirasthana 8",
            original_text="...",
            modern_evidence_status=EvidenceLevel.TRADITIONAL,
        ),
    )
    assert find_duplicates(unrelated, [original]) == []


def test_content_hash_is_stable_across_whitespace_differences() -> None:
    assert content_hash("Hello   world") == content_hash("hello world")


def test_semantic_similarity_identical_text_is_one() -> None:
    assert semantic_similarity(GOOD_CONTENT, GOOD_CONTENT) == 1.0


def test_missing_pregnancy_stage_is_warning_not_rejection() -> None:
    doc = make_document(pregnancy_stage=None)
    report = check_document_quality(doc)
    assert report.accepted
    assert any(c.name == "pregnancy_relevance" for c in report.warnings)


def test_danger_sign_content_without_safety_tags_warns() -> None:
    doc = make_document(
        content=(
            "If you experience severe headache and blurred vision during pregnancy, "
            "contact your provider immediately for further evaluation, monitoring, and appropriate emergency-level clinical management without delay."
        ),
        safety_tags=[],
    )
    report = check_document_quality(doc)
    assert report.accepted  # WARN, not FAIL
    assert any(c.name == "safety_relevance" for c in report.warnings)


def test_danger_sign_content_with_safety_tags_passes_cleanly() -> None:
    doc = make_document(
        content=(
            "If you experience severe headache and blurred vision during pregnancy, "
            "contact your provider immediately for further evaluation, monitoring, and appropriate emergency-level clinical management without delay."
        ),
        safety_tags=["requires_clinical_review"],
    )
    report = check_document_quality(doc)
    safety_check = next(c for c in report.checks if c.name == "safety_relevance")
    assert safety_check.passed
