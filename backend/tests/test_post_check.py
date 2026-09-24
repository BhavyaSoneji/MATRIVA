import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.context_packet import build_context_packet
from app.safety.classifier import RiskCategory, SafetyClassification
from app.safety.post_check import (
    SAFE_FALLBACK_RESPONSE,
    detect_dangerous_recommendations,
    detect_evidence_mismatch,
    detect_missing_escalation,
    detect_source_inconsistency,
    detect_unsupported_medical_claims,
    run_post_check,
    validate_and_finalize,
)
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk


def make_chunk(chunk_id: str, evidence_level: EvidenceLevel = EvidenceLevel.SUPPORTED) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        source_id="src-1",
        domain=Domain.NUTRITION,
        evidence_level=evidence_level,
        content="grounded content",
        chunk_index=0,
    )


def make_packet(chunks: list[KnowledgeChunk] | None = None):
    chunks = chunks or []
    return build_context_packet("question", [(c, 1.0) for c in chunks], safety_result={})


# --- 1. unsupported medical claim detection -----------------------------------

def test_unsupported_claim_flagged_when_no_citations() -> None:
    packet = make_packet([])
    hits = detect_unsupported_medical_claims("You have preeclampsia, definitely safe to ignore.", packet)
    assert hits


def test_claim_not_flagged_when_backed_by_verified_citation() -> None:
    chunk = make_chunk("c1")
    packet = make_packet([chunk])
    response = "You have a healthy pregnancy [c1]. This will cure nothing on its own [c1]."
    hits = detect_unsupported_medical_claims(response, packet)
    assert hits == []


def test_no_claim_phrases_no_flag() -> None:
    packet = make_packet([])
    assert detect_unsupported_medical_claims("Here is some general nutrition guidance.", packet) == []


# --- 2. dangerous recommendation detection ------------------------------------

def test_dangerous_recommendation_flagged() -> None:
    hits = detect_dangerous_recommendations("You don't need a doctor for this, just ignore it.")
    assert hits


def test_safe_response_not_flagged_as_dangerous() -> None:
    assert detect_dangerous_recommendations("Please consult your doctor about this.") == []


# --- 3. missing escalation detection ------------------------------------------

def test_missing_escalation_flagged_when_urgent_and_no_escalation_language() -> None:
    pre_check = SafetyClassification(risk_category=RiskCategory.URGENT_ESCALATION)
    assert detect_missing_escalation("Here is some general advice about diet.", pre_check) is True


def test_escalation_present_not_flagged() -> None:
    pre_check = SafetyClassification(risk_category=RiskCategory.URGENT_ESCALATION)
    assert detect_missing_escalation("Please seek emergency medical attention now.", pre_check) is False


def test_no_precheck_result_never_flags_missing_escalation() -> None:
    assert detect_missing_escalation("anything at all", None) is False


def test_safe_general_precheck_never_requires_escalation() -> None:
    pre_check = SafetyClassification(risk_category=RiskCategory.SAFE_GENERAL)
    assert detect_missing_escalation("Here is some general advice.", pre_check) is False


# --- 4. source consistency check ----------------------------------------------

def test_source_consistent_when_citation_is_real() -> None:
    chunk = make_chunk("c1")
    packet = make_packet([chunk])
    assert detect_source_inconsistency("Eat iron-rich foods [c1].", packet) is False


def test_source_inconsistent_when_citation_is_fake() -> None:
    chunk = make_chunk("c1")
    packet = make_packet([chunk])
    assert detect_source_inconsistency("Eat iron-rich foods [fake-id-99].", packet) is True


# --- 5. evidence mismatch detection -------------------------------------------

def test_evidence_mismatch_flagged_for_traditional_only_with_absolute_language() -> None:
    chunk = make_chunk("c1", evidence_level=EvidenceLevel.TRADITIONAL)
    packet = make_packet([chunk])
    hits = detect_evidence_mismatch("This remedy is clinically proven to work.", packet)
    assert hits


def test_no_mismatch_when_supported_evidence_present() -> None:
    chunk = make_chunk("c1", evidence_level=EvidenceLevel.SUPPORTED)
    packet = make_packet([chunk])
    assert detect_evidence_mismatch("This is clinically proven.", packet) == []


def test_no_mismatch_when_traditional_but_no_absolute_language() -> None:
    chunk = make_chunk("c1", evidence_level=EvidenceLevel.TRADITIONAL)
    packet = make_packet([chunk])
    assert detect_evidence_mismatch("Traditional practice suggests this may help.", packet) == []


# --- combined run_post_check / fail-closed behavior ---------------------------

def test_clean_response_passes_all_checks() -> None:
    chunk = make_chunk("c1")
    packet = make_packet([chunk])
    report = run_post_check("Eat iron-rich foods like spinach [c1].", packet)
    assert report.passed
    assert report.failed_checks == []


def test_any_single_failure_fails_the_whole_report() -> None:
    packet = make_packet([])
    report = run_post_check("You don't need a doctor, just ignore it.", packet)
    assert not report.passed
    assert "dangerous_recommendation" in report.failed_checks


def test_validate_and_finalize_returns_original_when_clean() -> None:
    chunk = make_chunk("c1")
    packet = make_packet([chunk])
    response = "Eat iron-rich foods like spinach [c1]."
    result, report = validate_and_finalize(response, packet)
    assert result == response
    assert report.passed


def test_validate_and_finalize_never_returns_raw_response_on_failure() -> None:
    """Section 21: DO NOT return the raw LLM response if any check fails."""
    packet = make_packet([])
    dangerous_response = "You don't need a doctor, just ignore it and skip your checkup."
    result, report = validate_and_finalize(dangerous_response, packet)
    assert result == SAFE_FALLBACK_RESPONSE
    assert result != dangerous_response
    assert not report.passed


def test_missing_escalation_triggers_fallback_via_validate_and_finalize() -> None:
    packet = make_packet([])
    pre_check = SafetyClassification(risk_category=RiskCategory.URGENT_ESCALATION)
    result, report = validate_and_finalize("Just take it easy, nothing to worry about.", packet, pre_check)
    assert result == SAFE_FALLBACK_RESPONSE
    assert "missing_escalation" in report.failed_checks
