"""Safety post-check validator (issue #13, Master Prompt Section 21).

After LLM generation, run 5 independent checks. If any fails, the raw LLM
response must never be returned -- regenerate, or (the path implemented
here) return a safe fallback per Section 22.

Rule-based, same philosophy as #12/#67 -- Section 19: "Never rely only on
the LLM." These are necessarily approximate (a rule-based system can't fully
verify medical claim correctness), so treat this as a coarse safety net,
not a substitute for the retrieval/citation pipeline (#6-#10) doing its job
correctly in the first place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.evidence.citation_validation import validate_citations_against_packet
from app.rag.context_packet import ContextPacket
from app.safety.classifier import RiskCategory, SafetyClassification

_MEDICAL_CLAIM_PHRASES = [
    "you have", "this will cure", "this cures", "guaranteed to", "definitely safe",
    "is caused by", "will prevent", "will treat", "clinically proven",
    "scientifically confirmed", "medically guaranteed",
]

_DANGEROUS_RECOMMENDATION_PHRASES = [
    "you don't need a doctor", "you do not need a doctor", "no need to worry",
    "ignore it", "ignore this", "safe to skip", "stop taking your medication",
    "you can skip your checkup", "no need to see a doctor",
]

_ESCALATION_LANGUAGE = [
    "doctor", "professional", "emergency", "seek care", "medical attention",
    "healthcare provider", "obstetric", "hospital",
]

# Absolute-certainty language that should never be used for traditional-only
# evidence (Section 11: never imply traditional knowledge has modern
# clinical validation unless the evidence explicitly supports that claim).
_ABSOLUTE_CERTAINTY_PHRASES = [
    "clinically proven", "scientifically confirmed", "medically guaranteed",
    "scientifically proven",
]


def _contains_any(text: str, phrases: list[str]) -> list[str]:
    lowered = text.lower()
    return [
        phrase
        for phrase in phrases
        if re.search(r"\b" + re.escape(phrase) + r"\b", lowered)
    ]


@dataclass
class PostCheckReport:
    passed: bool
    failed_checks: list[str] = field(default_factory=list)
    details: dict[str, list[str]] = field(default_factory=dict)


def detect_unsupported_medical_claims(response: str, context_packet: ContextPacket) -> list[str]:
    """Flags medical-claim-shaped language with zero verified citations
    backing it -- a claim asserted with no grounding at all."""
    claim_hits = _contains_any(response, _MEDICAL_CLAIM_PHRASES)
    if not claim_hits:
        return []
    citation_result = validate_citations_against_packet(response, context_packet)
    if not citation_result.verified_citation_ids:
        return claim_hits
    return []


def detect_dangerous_recommendations(response: str) -> list[str]:
    """Section 22: no false reassurance, no telling the user to ignore
    symptoms, no unsafe self-treatment recommendations."""
    return _contains_any(response, _DANGEROUS_RECOMMENDATION_PHRASES)


def detect_missing_escalation(
    response: str, pre_check_result: SafetyClassification | None
) -> bool:
    """If the pre-check flagged HIGH_RISK/URGENT_ESCALATION, the response
    must actually contain escalation language -- returns True (problem) if
    escalation was required but absent."""
    if pre_check_result is None:
        return False
    if pre_check_result.risk_category not in (
        RiskCategory.HIGH_RISK,
        RiskCategory.URGENT_ESCALATION,
    ):
        return False
    return not _contains_any(response, _ESCALATION_LANGUAGE)


def detect_source_inconsistency(response: str, context_packet: ContextPacket) -> bool:
    """Reuses #10's citation validation: any citation not resolving to an
    actually-retrieved source, any invented URL, any fabricated page
    reference."""
    return not validate_citations_against_packet(response, context_packet).is_clean


def detect_evidence_mismatch(response: str, context_packet: ContextPacket) -> list[str]:
    """Section 11: never imply traditional-only evidence has modern clinical
    validation. Flags absolute-certainty language when the retrieved
    evidence backing the response is TRADITIONAL-only (no SUPPORTED
    evidence present)."""
    evidence_levels = set(context_packet.evidence_summary.evidence_level_counts.keys())
    if not evidence_levels or "SUPPORTED" in evidence_levels:
        return []
    if "TRADITIONAL" not in evidence_levels:
        return []
    return _contains_any(response, _ABSOLUTE_CERTAINTY_PHRASES)


def run_post_check(
    response: str,
    context_packet: ContextPacket,
    pre_check_result: SafetyClassification | None = None,
) -> PostCheckReport:
    """Run all 5 Section 21 checks. `passed=False` means the raw response
    must not be returned to the user."""
    details: dict[str, list[str]] = {}

    unsupported_claims = detect_unsupported_medical_claims(response, context_packet)
    if unsupported_claims:
        details["unsupported_medical_claim"] = unsupported_claims

    dangerous_recs = detect_dangerous_recommendations(response)
    if dangerous_recs:
        details["dangerous_recommendation"] = dangerous_recs

    if detect_missing_escalation(response, pre_check_result):
        details["missing_escalation"] = ["required escalation language not found in response"]

    if detect_source_inconsistency(response, context_packet):
        details["source_inconsistency"] = ["response contains unverifiable citations/URLs/pages"]

    evidence_mismatch = detect_evidence_mismatch(response, context_packet)
    if evidence_mismatch:
        details["evidence_mismatch"] = evidence_mismatch

    return PostCheckReport(passed=not details, failed_checks=list(details.keys()), details=details)


SAFE_FALLBACK_RESPONSE = (
    "I'm not able to confidently answer that right now in a way I can fully verify against "
    "trusted sources. To be safe, please consult your obstetric care provider for guidance on "
    "this question rather than relying on this answer."
)


def validate_and_finalize(
    response: str,
    context_packet: ContextPacket,
    pre_check_result: SafetyClassification | None = None,
) -> tuple[str, PostCheckReport]:
    """Fail-closed: returns (response, report) if all checks pass, or
    (SAFE_FALLBACK_RESPONSE, report) if any check fails. Never returns the
    raw LLM response when a check fails (Section 21)."""
    report = run_post_check(response, context_packet, pre_check_result)
    if report.passed:
        return response, report
    return SAFE_FALLBACK_RESPONSE, report
