"""Thin rule-based safety pre-check for the Round 1 demo (issue #67).

Scoped-down version of the full classifier in #12: a keyword/red-flag match
against standard WHO/FOGSI obstetric danger signs, run BEFORE RAG generation
(Master Prompt Section 20). On a match, short-circuits to a safe fallback
message (Section 22: acknowledge, direct to professional care, no diagnosis,
no false reassurance) instead of calling the LLM.

NOTE: the red-flag phrases below reflect the standard WHO/FOGSI obstetric
danger-sign list (widely published, not clinic-specific thresholds). Cross-
check against the actual FOGSI GCPR PDF and get Clinical Lead sign-off
(#75) before this graduates past the demo.
"""

from __future__ import annotations

import re
from typing import Any

# risk_category values reuse Master Prompt Section 19's taxonomy
# (SAFE_GENERAL / LOW_CONCERN / MEDICAL_REVIEW / HIGH_RISK / URGENT_ESCALATION /
# INSUFFICIENT_INFORMATION). The thin pre-check only distinguishes
# URGENT_ESCALATION vs SAFE_GENERAL - full risk stratification is #12.
RED_FLAGS: dict[str, list[str]] = {
    "vaginal_bleeding": ["bleeding", "spotting heavily", "blood coming"],
    "severe_headache_or_vision": [
        "severe headache", "blurred vision", "blurry vision", "seeing spots", "flashing lights",
    ],
    "reduced_fetal_movement": [
        "baby not moving", "baby stopped moving", "no movement from baby",
        "reduced fetal movement", "can't feel the baby move",
    ],
    "severe_abdominal_pain": ["severe abdominal pain", "severe stomach pain", "sharp abdominal pain"],
    "convulsions": ["seizure", "convulsion", "fits"],
    "fluid_leak": ["water broke", "fluid leaking", "leaking fluid"],
    "high_fever": ["high fever", "very high temperature"],
    "severe_swelling": ["severe swelling", "sudden swelling of face", "sudden swelling of hands"],
    "persistent_vomiting": ["can't stop vomiting", "persistent vomiting", "vomiting nonstop"],
}

FALLBACK_MESSAGE = (
    "I hear that you're concerned, and what you're describing could need prompt medical "
    "attention. I'm not able to assess or diagnose this myself, so please contact your "
    "obstetric care provider or go to the nearest emergency/maternity care facility now "
    "rather than waiting for a chat answer. If you feel this is an emergency, please seek "
    "in-person or emergency care immediately."
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    """Word-boundary match so a short phrase like "fits" doesn't false-
    positive inside an unrelated word like "benefits" or "outfits"."""
    return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None


def precheck(query: str) -> dict[str, Any]:
    """Run the thin safety pre-check on a raw user query.

    Returns:
        {
          "risk_category": "URGENT_ESCALATION" | "SAFE_GENERAL",
          "matched_signs": [<red-flag keys that matched>],
          "message": <fallback string> | None,
        }

    Callers (e.g. the /chat endpoint) must check `risk_category` and, if
    URGENT_ESCALATION, return `message` directly WITHOUT calling the LLM/RAG
    pipeline.
    """
    normalized = _normalize(query)
    matched = [
        category
        for category, phrases in RED_FLAGS.items()
        if any(_contains_phrase(normalized, phrase) for phrase in phrases)
    ]

    if matched:
        return {
            "risk_category": "URGENT_ESCALATION",
            "matched_signs": matched,
            "message": FALLBACK_MESSAGE,
        }

    return {
        "risk_category": "SAFE_GENERAL",
        "matched_signs": [],
        "message": None,
    }


if __name__ == "__main__":
    test_phrases = [
        "I'm bleeding and it's scaring me",
        "I have a severe headache and blurred vision today",
        "My baby stopped moving since yesterday",
        "What should I eat in my second trimester?",
    ]
    for phrase in test_phrases:
        result = precheck(phrase)
        print(f"{phrase!r} -> {result['risk_category']} {result['matched_signs']}")
