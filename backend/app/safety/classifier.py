"""Full safety pre-check classifier (issue #12, Master Prompt Section 19 & 20).

Independent module -- never rely only on the LLM (Section 19). Classifies
incoming queries into one of the 6 Section 19 risk categories and routes
accordingly BEFORE RAG generation runs (Section 20). Supersedes #67's thin
keyword-only version for production use; #67's `pre_check.py` is left intact
in case a caller is already wired to it -- migrate callers to this module.

IMPORTANT -- clinical thresholds are NOT invented here. Section 19: "The
exact clinical rules must come from qualified medical reviewers and
authoritative clinical guidance. Do not invent medical thresholds." The
phrase lists below are illustrative, drawn from the same standard published
obstetric guidance #67 used -- NOT clinically validated thresholds. Every
category is `PENDING_CLINICAL_REVIEW` and must be signed off by the Clinical
Lead (#75) before being presented as clinically validated, same as #67.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

from app.models import RiskLevel, SafetyRule, SafetyStatus


class RiskCategory(StrEnum):
    SAFE_GENERAL = "SAFE_GENERAL"
    LOW_CONCERN = "LOW_CONCERN"
    MEDICAL_REVIEW = "MEDICAL_REVIEW"
    HIGH_RISK = "HIGH_RISK"
    URGENT_ESCALATION = "URGENT_ESCALATION"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


def _contains_phrase(text: str, phrase: str) -> bool:
    """Word-boundary, case-insensitive match (see #58's fix to #67 for why
    plain substring matching is unsafe here, e.g. "fits" inside "benefits")."""
    return re.search(r"\b" + re.escape(phrase.lower()) + r"\b", text.lower()) is not None


# Section 20's 8 categories to analyze for, mapped to a Section 19 risk
# category. Ordered most-severe-first: iteration stops at the first group
# that matches, so an emergency symptom always outranks a milder match.

_EMERGENCY_SYMPTOMS = [
    "bleeding", "spotting heavily", "severe headache", "blurred vision",
    "blurry vision", "seeing spots", "flashing lights", "baby not moving",
    "baby stopped moving", "reduced fetal movement", "severe abdominal pain",
    "seizure", "convulsion", "fits", "water broke", "leaking fluid",
    "high fever", "severe swelling", "can't stop vomiting", "persistent vomiting",
]  # emergency-like symptoms

_DANGEROUS_REQUESTS = [
    "induce labor myself", "home abortion", "terminate the pregnancy myself",
    "self medicate", "self-medicate",
]  # potentially dangerous requests

_HIGH_RISK_CONTEXT = [
    "preeclampsia", "eclampsia", "gestational diabetes", "placenta previa",
    "previous miscarriage", "high risk pregnancy", "high-risk pregnancy",
]  # high-risk pregnancy context

_CHANGE_TREATMENT_REQUESTS = [
    "stop taking my medication", "stop my medication", "increase my dose",
    "change my medication without", "skip my medication",
]  # requests to change treatment

_REPLACE_PROFESSIONAL_ADVICE = [
    "instead of seeing a doctor", "instead of my doctor", "avoid the hospital",
    "skip my checkup", "don't need a doctor", "do not need a doctor",
]  # requests to replace professional medical advice

_MEDICATION_QUESTIONS = [
    "can i take", "is this medicine safe", "dosage of", "drug interaction",
    "medication safe during pregnancy",
]  # medication questions

_CONTRAINDICATION_QUESTIONS = [
    "contraindication", "interact with", "interacts with", "allergic to",
    "safe with my condition",
]  # contraindication-related questions

_DIAGNOSIS_REQUESTS = [
    "do i have", "diagnose me", "what disease do i have", "what condition do i have",
    "am i sick with",
]  # requests for diagnosis

_LOW_CONCERN_SYMPTOMS = [
    "mild nausea", "slight backache", "occasional heartburn", "mild cramping",
    "a little tired",
]

CATEGORY_RULES: list[tuple[list[str], RiskCategory]] = [
    (_EMERGENCY_SYMPTOMS, RiskCategory.URGENT_ESCALATION),
    (_DANGEROUS_REQUESTS, RiskCategory.HIGH_RISK),
    (_HIGH_RISK_CONTEXT, RiskCategory.HIGH_RISK),
    (_CHANGE_TREATMENT_REQUESTS, RiskCategory.HIGH_RISK),
    (_REPLACE_PROFESSIONAL_ADVICE, RiskCategory.HIGH_RISK),
    (_MEDICATION_QUESTIONS, RiskCategory.MEDICAL_REVIEW),
    (_CONTRAINDICATION_QUESTIONS, RiskCategory.MEDICAL_REVIEW),
    (_DIAGNOSIS_REQUESTS, RiskCategory.MEDICAL_REVIEW),
    (_LOW_CONCERN_SYMPTOMS, RiskCategory.LOW_CONCERN),
]

_INSUFFICIENT_INFO_WORD_COUNT = 3

_SHORT_CIRCUIT_CATEGORIES = frozenset({RiskCategory.HIGH_RISK, RiskCategory.URGENT_ESCALATION})

_FALLBACK_MESSAGES: dict[RiskCategory, str] = {
    RiskCategory.URGENT_ESCALATION: (
        "I hear that you're concerned, and what you're describing could need prompt medical "
        "attention. I'm not able to assess or diagnose this myself, so please contact your "
        "obstetric care provider or go to the nearest emergency/maternity care facility now "
        "rather than waiting for a chat answer."
    ),
    RiskCategory.HIGH_RISK: (
        "This touches something that really needs your own doctor's judgment rather than a "
        "general answer here -- please talk to your obstetric care provider before making any "
        "decision about this, especially around medication, treatment changes, or high-risk "
        "pregnancy conditions."
    ),
    RiskCategory.INSUFFICIENT_INFORMATION: (
        "I want to make sure I understand your question correctly -- could you share a bit more "
        "detail about what you're asking?"
    ),
}


@dataclass
class SafetyClassification:
    risk_category: RiskCategory
    matched_phrases: list[str] = field(default_factory=list)
    requires_short_circuit: bool = False
    message: str | None = None


def classify(query: str) -> SafetyClassification:
    """Classify `query` into one of the 6 Section 19 risk categories and
    decide routing per Section 20 ("if the query requires professional
    medical attention, do not continue as a normal recommendation query").

    Per this issue's acceptance criteria, `requires_short_circuit` is True
    only for HIGH_RISK/URGENT_ESCALATION -- MEDICAL_REVIEW/LOW_CONCERN still
    proceed to RAG generation (with the classification available for the
    caller to add appropriate caveats), and INSUFFICIENT_INFORMATION signals
    a clarifying question is needed rather than a safety block.
    """
    for phrases, category in CATEGORY_RULES:
        hits = [p for p in phrases if _contains_phrase(query, p)]
        if hits:
            return SafetyClassification(
                risk_category=category,
                matched_phrases=hits,
                requires_short_circuit=category in _SHORT_CIRCUIT_CATEGORIES,
                message=_FALLBACK_MESSAGES.get(category),
            )

    if len(query.split()) < _INSUFFICIENT_INFO_WORD_COUNT:
        return SafetyClassification(
            risk_category=RiskCategory.INSUFFICIENT_INFORMATION,
            message=_FALLBACK_MESSAGES[RiskCategory.INSUFFICIENT_INFORMATION],
        )

    return SafetyClassification(risk_category=RiskCategory.SAFE_GENERAL)


# --- API/database safety adapter ------------------------------------------
# The API supports administrator-managed safety rules in addition to the
# reviewed rule set used by the RAG evaluation pipeline.


class SafetySubsystemError(RuntimeError):
    """Raised when the independent safety layer cannot make a decision."""



@dataclass(frozen=True)
class SafetyDecision:
    status: SafetyStatus
    risk: RiskLevel
    matched_rule_ids: list[str] = field(default_factory=list)
    response: str | None = None
    reason: str = "No configured safety rule matched"


URGENT_TERMS = {
    "heavy bleeding", "bleeding heavily", "severe bleeding", "vaginal bleeding",
    "reduced fetal movement", "no fetal movement", "baby not moving", "severe headache",
    "severe abdominal pain", "chest pain", "difficulty breathing", "cannot breathe",
    "seizure", "fits", "fainting", "suicidal thoughts", "suicidal", "poisoning", "overdose",
}
MEDICAL_REVIEW_TERMS = {
    "medication", "medicine", "tablet", "prescription", "dose", "dosage", "antibiotic",
    "bleeding", "pain", "fever", "diagnosis", "diagnose", "is this normal", "should i worry",
}


def normalize_query(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"\s+", " ", value).strip()


def _risk_from_rule(value: str) -> RiskLevel:
    try:
        return RiskLevel(value)
    except ValueError:
        return RiskLevel.MEDICAL_REVIEW


def classify_query(query: str, rules: list[SafetyRule] | None = None) -> SafetyDecision:
    normalized = normalize_query(query)
    matched_ids: list[str] = []
    highest = RiskLevel.SAFE_GENERAL
    response: str | None = None
    reason = "No configured safety rule matched"

    for term in URGENT_TERMS:
        if term in normalized:
            matched_ids.append(f"builtin:{term}")
            highest = RiskLevel.URGENT_ESCALATION
            reason = f"Matched urgent safety term: {term}"

    for term in MEDICAL_REVIEW_TERMS:
        if term in normalized and highest != RiskLevel.URGENT_ESCALATION:
            matched_ids.append(f"builtin:{term}")
            highest = RiskLevel.MEDICAL_REVIEW
            response = "This question may need a clinician's review. Please do not change medication or treatment based on this response; contact your maternity-care professional."
            reason = f"Matched review term: {term}"

    for rule in rules or []:
        pattern = normalize_query(rule.pattern)
        if pattern and pattern in normalized:
            matched_ids.append(rule.id)
            rule_risk = _risk_from_rule(rule.risk_level)
            if rule_risk == RiskLevel.URGENT_ESCALATION or highest == RiskLevel.URGENT_ESCALATION:
                highest = RiskLevel.URGENT_ESCALATION
            elif rule_risk == RiskLevel.HIGH_RISK and highest not in {RiskLevel.URGENT_ESCALATION}:
                highest = RiskLevel.HIGH_RISK
            elif highest == RiskLevel.SAFE_GENERAL:
                highest = rule_risk
            response = rule.response
            reason = f"Matched reviewed safety rule: {rule.name}"

    if highest == RiskLevel.URGENT_ESCALATION:
        response = (
            "I’m concerned about the symptoms you described. This needs urgent assessment by a maternity-care professional. "
            "If you have severe or worsening symptoms, contact your local emergency service now. I cannot diagnose or replace emergency care."
        )
    elif highest == RiskLevel.HIGH_RISK:
        response = response or (
            "This question may involve a health risk that should be reviewed by a qualified maternity-care professional. "
            "I cannot diagnose or recommend changing treatment here."
        )

    status_map = {
        RiskLevel.SAFE_GENERAL: SafetyStatus.SAFE_GENERAL,
        RiskLevel.LOW_CONCERN: SafetyStatus.LOW_CONCERN,
        RiskLevel.MEDICAL_REVIEW: SafetyStatus.MEDICAL_REVIEW,
        RiskLevel.HIGH_RISK: SafetyStatus.HIGH_RISK,
        RiskLevel.URGENT_ESCALATION: SafetyStatus.URGENT_ESCALATION,
    }
    return SafetyDecision(
        status=status_map[highest],
        risk=highest,
        matched_rule_ids=list(dict.fromkeys(matched_ids)),
        response=response,
        reason=reason,
    )


@dataclass(frozen=True)
class PostCheckResult:
    valid: bool
    reason: str
    safe_answer: str | None = None


DANGEROUS_PHRASES = (
    "stop taking your medication", "skip your medication", "double your dose",
    "no need to see a doctor", "you do not need medical care", "ignore the warning signs",
)


def validate_generated_answer(
    answer: str,
    *,
    source_ids: list[str],
    citation_ids: list[str],
    decision: SafetyDecision,
    require_source: bool = True,
) -> PostCheckResult:
    normalized = normalize_query(answer)
    if not normalized:
        return PostCheckResult(False, "Generated answer is empty", "I cannot safely answer this question from the currently reviewed information.")
    if decision.risk in {RiskLevel.HIGH_RISK, RiskLevel.URGENT_ESCALATION} and not any(
        term in normalized for term in ("professional", "emergency", "doctor", "clinician", "maternity")
    ):
        return PostCheckResult(False, "High-risk answer omitted escalation", decision.response)
    if any(phrase in normalized for phrase in DANGEROUS_PHRASES):
        return PostCheckResult(False, "Generated answer contained a dangerous recommendation", "I cannot safely provide that recommendation. Please contact a qualified maternity-care professional.")
    if set(citation_ids) - set(source_ids):
        return PostCheckResult(False, "Generated answer cited a source that was not retrieved", "I cannot verify the sources for this response, so I am not providing it.")
    if require_source and not source_ids:
        return PostCheckResult(False, "No approved source was retrieved", "I don’t have enough currently reviewed information to answer this safely. Please consult your maternity-care professional.")
    return PostCheckResult(True, "Post-checks passed")


def insufficient_evidence() -> str:
    return "I don’t have enough currently reviewed information to answer this safely. Please consult your maternity-care professional or ask us to review an appropriate source."
