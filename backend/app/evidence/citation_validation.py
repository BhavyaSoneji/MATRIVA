"""Citation validation (issue #10, Master Prompt Section 12 Step 11 + Section 18).

Post-generation check: every citation in the LLM response must map to an
actually-retrieved source. Fails closed -- unverifiable citations, invented
URLs, and fabricated page references are stripped/flagged rather than passed
through to the user.

Note on page numbers: `KnowledgeChunk` (#1) doesn't carry page metadata yet,
so ANY page-number reference in generated output is currently unverifiable
by definition and is treated as fabricated per Section 18 ("never fabricate
page numbers") until page metadata is added to the schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.rag.context_packet import ContextPacket

_CITATION_PATTERN = re.compile(r"\[([A-Za-z0-9_\-]+)\]")
_URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+")
_PAGE_PATTERN = re.compile(r"\b(?:page|p\.?)\s*\d+\b", re.IGNORECASE)

UNVERIFIABLE_CITATION_PLACEHOLDER = "[citation removed: not found among retrieved sources]"
FABRICATED_URL_PLACEHOLDER = "[URL removed: not present in retrieved sources]"
FABRICATED_PAGE_PLACEHOLDER = "[page reference removed: not verifiable]"


@dataclass
class CitationValidationResult:
    cleaned_answer: str
    verified_citation_ids: list[str] = field(default_factory=list)
    unverifiable_citation_ids: list[str] = field(default_factory=list)
    fabricated_urls: list[str] = field(default_factory=list)
    fabricated_page_references: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (
            self.unverifiable_citation_ids
            or self.fabricated_urls
            or self.fabricated_page_references
        )


def validate_citations(answer: str, retrieved_source_ids: set[str]) -> CitationValidationResult:
    """Validate `[id]`-style citations in `answer` against the set of ids
    that were actually retrieved (chunk_id/document_id/source_id), strip any
    invented URLs, and strip any page-number references (unverifiable, see
    module docstring)."""
    verified: list[str] = []
    unverifiable: list[str] = []

    def _check_citation(match: re.Match[str]) -> str:
        citation_id = match.group(1)
        if citation_id in retrieved_source_ids:
            verified.append(citation_id)
            return match.group(0)
        unverifiable.append(citation_id)
        return UNVERIFIABLE_CITATION_PLACEHOLDER

    cleaned = _CITATION_PATTERN.sub(_check_citation, answer)

    fabricated_urls = _URL_PATTERN.findall(cleaned)
    cleaned = _URL_PATTERN.sub(FABRICATED_URL_PLACEHOLDER, cleaned)

    fabricated_pages = _PAGE_PATTERN.findall(cleaned)
    cleaned = _PAGE_PATTERN.sub(FABRICATED_PAGE_PLACEHOLDER, cleaned)

    return CitationValidationResult(
        cleaned_answer=cleaned,
        verified_citation_ids=verified,
        unverifiable_citation_ids=unverifiable,
        fabricated_urls=fabricated_urls,
        fabricated_page_references=fabricated_pages,
    )


def validate_citations_against_packet(
    answer: str, context_packet: ContextPacket
) -> CitationValidationResult:
    """Convenience wrapper: builds the valid-id set from a #8 ContextPacket's
    actually-retrieved sources (chunk_id, document_id, and source_id are all
    acceptable citation forms), plus any external web sources (web_id) the
    Section 43 gate pulled in via app.rag.web_search -- a citation marker
    like "[web1]" naming one of THOSE must not be stripped as unverifiable
    just because it isn't a local knowledge-base id. This does not weaken
    the check: the id still must resolve to something actually retrieved
    (now including web results), and any URL/page text is still stripped
    exactly as before -- web citations are surfaced to the user structurally
    (see app.services.chat), not by trusting the model to print a raw URL."""
    valid_ids: set[str] = set()
    for source in context_packet.retrieved_sources:
        valid_ids.add(source.chunk_id)
        valid_ids.add(source.document_id)
        valid_ids.add(source.source_id)
    for web_source in context_packet.web_sources:
        valid_ids.add(web_source.web_id)
    return validate_citations(answer, valid_ids)
