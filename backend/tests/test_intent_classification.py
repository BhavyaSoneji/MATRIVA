import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.intent_classification import ChatIntent, classify_intent

CATEGORY_EXAMPLES = [
    ("What should I eat for good nutrition during pregnancy?", ChatIntent.NUTRITION),
    ("Is it safe to eat papaya while pregnant?", ChatIntent.FOOD),
    ("What exercise or yoga is safe in the second trimester?", ChatIntent.EXERCISE),
    ("What should my daily routine and sleep schedule look like?", ChatIntent.LIFESTYLE),
    ("I've been feeling anxious and stressed lately, is that normal?", ChatIntent.MENTAL_WELLBEING),
    ("When is my next ANC visit and ultrasound scan?", ChatIntent.ANTENATAL_CARE),
    ("How does the fetus develop in the third trimester?", ChatIntent.PREGNANCY_DEVELOPMENT),
    ("What does Ayurveda say about garbhini paricharya?", ChatIntent.AYURVEDA),
    ("My grandmother said to follow this traditional practice, is it fine?", ChatIntent.TRADITIONAL_PRACTICE),
    ("I have some pain and swelling, should I be concerned about this symptom?", ChatIntent.MEDICAL_CONCERN),
    ("What is the correct dosage for this prescription medication?", ChatIntent.MEDICATION),
    ("This is an emergency, I can't breathe properly!", ChatIntent.EMERGENCY),
    ("Hi there, I'm pregnant and have a general question.", ChatIntent.GENERAL),
    ("What's the weather like today?", ChatIntent.OTHER),
]


def test_covers_at_least_one_example_per_category() -> None:
    covered = {intent for _, intent in CATEGORY_EXAMPLES}
    assert covered == set(ChatIntent)


def test_each_example_classifies_as_expected() -> None:
    for query, expected_intent in CATEGORY_EXAMPLES:
        assert classify_intent(query) == expected_intent, f"failed for: {query!r}"


def test_returns_a_chat_intent_member_for_arbitrary_query() -> None:
    result = classify_intent("anything at all")
    assert isinstance(result, ChatIntent)


def test_safety_urgent_escalation_overrides_classification() -> None:
    """Section 30: safety rules always have higher priority."""
    query = "What should I eat for nutrition?"  # would normally classify as NUTRITION
    safety_result = {"risk_category": "URGENT_ESCALATION", "message": "seek care"}
    assert classify_intent(query, safety_result=safety_result) == ChatIntent.EMERGENCY


def test_safe_general_safety_result_does_not_override() -> None:
    query = "What should I eat for nutrition?"
    safety_result = {"risk_category": "SAFE_GENERAL", "message": None}
    assert classify_intent(query, safety_result=safety_result) == ChatIntent.NUTRITION
