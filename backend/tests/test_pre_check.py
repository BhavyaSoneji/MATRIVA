import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.safety.pre_check import precheck


def test_bleeding_triggers_urgent_escalation() -> None:
    result = precheck("I'm bleeding and it's scaring me")
    assert result["risk_category"] == "URGENT_ESCALATION"
    assert "vaginal_bleeding" in result["matched_signs"]
    assert result["message"] is not None


def test_severe_headache_and_vision_change_triggers_urgent_escalation() -> None:
    result = precheck("I have a severe headache and blurred vision today")
    assert result["risk_category"] == "URGENT_ESCALATION"
    assert "severe_headache_or_vision" in result["matched_signs"]


def test_reduced_fetal_movement_triggers_urgent_escalation() -> None:
    result = precheck("My baby stopped moving since yesterday")
    assert result["risk_category"] == "URGENT_ESCALATION"
    assert "reduced_fetal_movement" in result["matched_signs"]


def test_normal_nutrition_question_is_safe_general() -> None:
    result = precheck("What should I eat in my second trimester?")
    assert result["risk_category"] == "SAFE_GENERAL"
    assert result["matched_signs"] == []
    assert result["message"] is None


def test_fallback_message_acknowledges_and_directs_to_care() -> None:
    result = precheck("severe abdominal pain right now")
    assert "professional" in result["message"] or "emergency" in result["message"].lower()


def test_word_boundary_prevents_false_positive_on_substring() -> None:
    """Regression: "fits" (convulsions red flag) must not match inside
    unrelated words like "benefits" -- naive substring matching would
    incorrectly escalate this ordinary question."""
    result = precheck("What are the benefits of prenatal yoga and good outfits for exercise?")
    assert result["risk_category"] == "SAFE_GENERAL"
    assert result["matched_signs"] == []


def test_fits_still_matches_as_a_whole_word() -> None:
    result = precheck("She had convulsions and fits during the night")
    assert result["risk_category"] == "URGENT_ESCALATION"
    assert "convulsions" in result["matched_signs"]
