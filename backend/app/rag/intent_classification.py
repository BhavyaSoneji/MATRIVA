"""Chat intent classification (issue #57, Master Prompt Section 30).

Rule-based/keyword classifier for the 14 intent categories. Section 30 says
the classifier "may initially be LLM-based + rule-based safety overrides" --
LLM-based is offered as an option, not a requirement, and this project's own
principle (Section 12: "Do not make the LLM responsible for everything")
favors starting deterministic and rule-based, same approach #67's safety
pre-check took. Swap in an LLM-assisted classifier later if keyword coverage
proves insufficient; the safety-override contract stays the same either way.

Safety rules always have higher priority (Section 30): if a safety_result
indicates URGENT_ESCALATION, that overrides whatever the keyword classifier
would have said, and the intent is forced to EMERGENCY.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ChatIntent(StrEnum):
    NUTRITION = "NUTRITION"
    EXERCISE = "EXERCISE"
    LIFESTYLE = "LIFESTYLE"
    MENTAL_WELLBEING = "MENTAL_WELLBEING"
    ANTENATAL_CARE = "ANTENATAL_CARE"
    PREGNANCY_DEVELOPMENT = "PREGNANCY_DEVELOPMENT"
    AYURVEDA = "AYURVEDA"
    TRADITIONAL_PRACTICE = "TRADITIONAL_PRACTICE"
    FOOD = "FOOD"
    MEDICAL_CONCERN = "MEDICAL_CONCERN"
    MEDICATION = "MEDICATION"
    EMERGENCY = "EMERGENCY"
    GENERAL = "GENERAL"
    OTHER = "OTHER"


# Ordered so that, on a tied keyword score, an earlier-listed (more safety-
# adjacent) category wins the tie.
_INTENT_KEYWORDS: dict[ChatIntent, list[str]] = {
    ChatIntent.EMERGENCY: ["emergency", "urgent", "can't breathe", "cannot breathe", "ambulance"],
    ChatIntent.MEDICAL_CONCERN: [
        "pain", "symptom", "concerned about", "worried about", "swelling", "cramp",
    ],
    ChatIntent.MEDICATION: [
        "medicine", "medication", "tablet", "dose", "dosage", "supplement",
        "prescription", "drug",
    ],
    ChatIntent.NUTRITION: [
        "nutrition", "diet", "vitamin", "protein", "iron", "calcium", "what should i eat",
        "meal plan",
    ],
    ChatIntent.FOOD: [
        "papaya", "pineapple", "fish", "raw egg", "spicy food", "coffee", "caffeine",
        "is it safe to eat",
    ],
    ChatIntent.EXERCISE: ["exercise", "yoga", "workout", "walk", "stretch", "physical activity"],
    ChatIntent.LIFESTYLE: ["sleep", "daily routine", "travel", "rest", "posture", "work schedule"],
    ChatIntent.MENTAL_WELLBEING: [
        "anxious", "anxiety", "depressed", "mood", "stress", "worry", "emotional",
    ],
    ChatIntent.ANTENATAL_CARE: [
        "checkup", "anc visit", "appointment", "ultrasound", "scan", "vaccination",
        "doctor visit",
    ],
    ChatIntent.PREGNANCY_DEVELOPMENT: [
        "trimester", "fetus", "embryo", "baby development", "growth week",
        "week of pregnancy",
    ],
    ChatIntent.AYURVEDA: [
        "ayurveda", "ayurvedic", "garbhini paricharya", "charaka", "dosha", "vata",
        "pitta", "kapha",
    ],
    ChatIntent.TRADITIONAL_PRACTICE: [
        "traditional practice", "ritual", "home remedy", "cultural custom", "grandmother said",
    ],
}

_GENERAL_KEYWORDS = ["pregnant", "pregnancy", "expecting a baby", "hello", "hi there"]


def _score(query: str, keywords: list[str]) -> int:
    lowered = query.lower()
    return sum(1 for kw in keywords if kw in lowered)


def classify_intent(query: str, safety_result: dict[str, Any] | None = None) -> ChatIntent:
    """Classify `query` into one of the 14 Section 30 intent categories.

    `safety_result` is the dict from #67/#12's safety pre-check
    (`{"risk_category": ..., ...}`). If it indicates URGENT_ESCALATION, that
    overrides the keyword classifier entirely -- safety always wins.
    """
    if safety_result and safety_result.get("risk_category") == "URGENT_ESCALATION":
        return ChatIntent.EMERGENCY

    scored = [(intent, _score(query, keywords)) for intent, keywords in _INTENT_KEYWORDS.items()]
    best_intent, best_score = max(scored, key=lambda pair: pair[1])
    if best_score > 0:
        return best_intent

    if _score(query, _GENERAL_KEYWORDS) > 0:
        return ChatIntent.GENERAL

    return ChatIntent.OTHER
