import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.safety.classifier import RiskCategory, classify


def test_emergency_symptom_triggers_urgent_escalation() -> None:
    result = classify("I'm bleeding and it's scaring me")
    assert result.risk_category == RiskCategory.URGENT_ESCALATION
    assert result.requires_short_circuit
    assert result.message is not None


def test_dangerous_request_triggers_high_risk() -> None:
    result = classify("How can I induce labor myself at home?")
    assert result.risk_category == RiskCategory.HIGH_RISK
    assert result.requires_short_circuit


def test_high_risk_pregnancy_context_triggers_high_risk() -> None:
    result = classify("I was diagnosed with preeclampsia, what should I know?")
    assert result.risk_category == RiskCategory.HIGH_RISK
    assert result.requires_short_circuit


def test_change_treatment_request_triggers_high_risk() -> None:
    result = classify("Can I just stop taking my medication on my own?")
    assert result.risk_category == RiskCategory.HIGH_RISK


def test_replace_professional_advice_request_triggers_high_risk() -> None:
    result = classify("Is it fine to skip my checkup instead of seeing a doctor?")
    assert result.risk_category == RiskCategory.HIGH_RISK


def test_medication_question_triggers_medical_review() -> None:
    result = classify("Can I take ibuprofen while pregnant?")
    assert result.risk_category == RiskCategory.MEDICAL_REVIEW
    assert not result.requires_short_circuit


def test_contraindication_question_triggers_medical_review() -> None:
    result = classify("Does this supplement interact with my thyroid medication?")
    assert result.risk_category == RiskCategory.MEDICAL_REVIEW


def test_diagnosis_request_triggers_medical_review() -> None:
    result = classify("Do I have anemia based on these symptoms?")
    assert result.risk_category == RiskCategory.MEDICAL_REVIEW


def test_high_risk_context_outranks_diagnosis_request_when_both_match() -> None:
    """A query naming a genuinely high-risk condition gets the higher-
    severity routing even if also phrased as a diagnosis request."""
    result = classify("Do I have gestational diabetes based on these symptoms?")
    assert result.risk_category == RiskCategory.HIGH_RISK


def test_low_concern_symptom() -> None:
    result = classify("I've had mild nausea in the mornings, is that normal?")
    assert result.risk_category == RiskCategory.LOW_CONCERN
    assert not result.requires_short_circuit


def test_normal_question_is_safe_general() -> None:
    result = classify("What are some good sources of iron during pregnancy?")
    assert result.risk_category == RiskCategory.SAFE_GENERAL
    assert not result.requires_short_circuit
    assert result.message is None


def test_very_short_query_is_insufficient_information() -> None:
    result = classify("food?")
    assert result.risk_category == RiskCategory.INSUFFICIENT_INFORMATION
    assert result.message is not None


def test_only_high_risk_and_urgent_escalation_short_circuit() -> None:
    for category in RiskCategory:
        expected_short_circuit = category in (
            RiskCategory.HIGH_RISK,
            RiskCategory.URGENT_ESCALATION,
        )
        # sanity: confirm the module's own constant matches the acceptance criteria
        from app.safety.classifier import _SHORT_CIRCUIT_CATEGORIES

        assert (category in _SHORT_CIRCUIT_CATEGORIES) == expected_short_circuit


def test_word_boundary_prevents_false_positive_on_fits_substring() -> None:
    result = classify("What are the benefits of prenatal yoga and good outfits for exercise?")
    assert result.risk_category == RiskCategory.SAFE_GENERAL


def test_emergency_symptom_takes_priority_over_lower_severity_match() -> None:
    """If a query matches both an emergency symptom and a lower-severity
    category, the higher-severity classification wins."""
    result = classify("I have mild nausea but also severe abdominal pain")
    assert result.risk_category == RiskCategory.URGENT_ESCALATION
