"""Multi-domain query decomposition & response segmentation (issue #58,
Master Prompt Section 31).

Two pieces:
1. `detect_domains(query)`: multi-label domain detection (unlike #57's
   single-label intent classifier) so a query touching nutrition + region +
   Ayurveda triggers retrieval across all of them (feeds #6's hybrid_retrieve
   `domains` filter).
2. Response segmentation: when retrieved evidence actually spans both
   AYURVEDA and a non-Ayurveda domain, the system prompt must instruct the
   LLM to separate MODERN MEDICAL INFORMATION / TRADITIONAL-AYURVEDIC
   INFORMATION / EVIDENCE STATUS rather than blending them, and
   `validate_segmentation` checks the generated response actually did so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.rag.keyword_search import contains_phrase
from app.schemas.knowledge import Domain

_DOMAIN_KEYWORDS: dict[Domain, list[str]] = {
    Domain.MODERN_MEDICAL: [
        "medical", "doctor", "clinical", "diagnosis", "risk", "health condition",
        "medically safe",
    ],
    Domain.AYURVEDA: [
        "ayurveda", "ayurvedic", "garbhini paricharya", "dosha", "charaka",
        "traditional medicine",
    ],
    Domain.NUTRITION: [
        "food", "eat", "diet", "nutrition", "meal", "vitamin", "vegetarian", "vegan",
    ],
    Domain.LIFESTYLE: ["exercise", "sleep", "routine", "yoga", "stress", "daily activity"],
    Domain.REGIONAL_CULTURAL: [
        "gujarati", "punjabi", "kerala", "bengali", "regional", "local food", "cultural",
    ],
}

MODERN_SECTION = "MODERN MEDICAL INFORMATION"
TRADITIONAL_SECTION = "TRADITIONAL/AYURVEDIC INFORMATION"
EVIDENCE_STATUS_SECTION = "EVIDENCE STATUS"
REQUIRED_SECTIONS = (MODERN_SECTION, TRADITIONAL_SECTION, EVIDENCE_STATUS_SECTION)

MULTI_DOMAIN_PROMPT_ADDENDUM = f"""
This question touches multiple knowledge domains, including traditional/Ayurvedic content
alongside other information. Structure your answer using exactly these section headers, in this
order:

{MODERN_SECTION}

{TRADITIONAL_SECTION}

{EVIDENCE_STATUS_SECTION}

Do not blend modern medical/nutrition/lifestyle content and traditional/Ayurvedic content
together under one heading."""


def detect_domains(query: str) -> list[Domain]:
    """Multi-label domain detection: return every Domain whose keywords
    appear in the query (not just the single best match)."""
    return [
        domain
        for domain, keywords in _DOMAIN_KEYWORDS.items()
        if any(contains_phrase(query, kw) for kw in keywords)
    ]


def multi_domain_retrieval_filter(query: str) -> list[Domain] | None:
    """Feeds #6's hybrid_retrieve `domains` filter. Only constrain retrieval
    when genuinely multi-domain (2+ detected) -- a single or zero detection
    means "don't filter," per Section 13's over-filtering guidance."""
    domains = detect_domains(query)
    return domains if len(domains) > 1 else None


def requires_segmentation(evidence_domains: list[str]) -> bool:
    """True when the retrieved evidence spans both AYURVEDA and at least one
    non-Ayurveda domain -- the exact modern-vs-traditional split Section 31
    cares about."""
    domains = set(evidence_domains)
    return Domain.AYURVEDA in domains and len(domains - {Domain.AYURVEDA}) > 0


@dataclass
class SegmentationValidationResult:
    is_segmented: bool
    missing_sections: list[str] = field(default_factory=list)


def validate_segmentation(response_text: str) -> SegmentationValidationResult:
    """Post-generation check: did the response actually use the required
    section headers? (Structural check only -- doesn't verify content
    correctness, just that domains weren't blended under no headers.)"""
    missing = [section for section in REQUIRED_SECTIONS if section not in response_text]
    return SegmentationValidationResult(is_segmented=not missing, missing_sections=missing)
