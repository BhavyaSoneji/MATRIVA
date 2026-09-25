"""Structured context packet construction (issue #8, Section 12 Step 8 + Section 16).

The LLM must receive: USER CONTEXT + USER QUESTION + RETRIEVED SOURCES +
SAFETY RESULT + EVIDENCE METADATA. This module assembles that packet from
#6/#7's retrieval+reranking output and #67's safety pre-check result, with
token-budget truncation so a large retrieval set doesn't blow the LLM's
context window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.rag.reranking import UserContext
from app.schemas.knowledge import KnowledgeChunk

DEFAULT_MAX_TOKENS = 2000
_NEEDS_REVIEW_STATUSES = {"UNVERIFIED", "PENDING_SOURCE_VERIFICATION", "PENDING_CLINICAL_REVIEW"}


def _token_count(text: str) -> int:
    return len(text.split())


@dataclass
class SourceEntry:
    chunk_id: str
    document_id: str
    source_id: str
    domain: str
    evidence_level: str
    review_status: str | None
    content: str


@dataclass(frozen=True)
class WebSourceEntry:
    """A live web search hit (see app.rag.web_search), reshaped for the
    context packet so it renders as a clearly separate, lower-confidence
    section of the prompt -- never mixed into RETRIEVED SOURCES.

    Reuses this codebase's existing evidence_level/source_type vocabulary
    (app.models.entities.EvidenceLevel/SourceType) rather than inventing a
    parallel one: source_type is always "external_web" and evidence_level is
    always "uncertain" -- an external, unverified page is never entitled to
    the same confidence as a reviewed local knowledge-base entry, regardless
    of how authoritative it looks.
    """

    web_id: str
    title: str
    url: str
    domain: str
    content: str
    source_type: str = "external_web"
    evidence_level: str = "uncertain"


@dataclass
class EvidenceSummary:
    domains: list[str]
    evidence_level_counts: dict[str, int]
    needs_review_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ContextPacket:
    user_context: dict[str, Any]
    user_question: str
    retrieved_sources: list[SourceEntry]
    safety_result: dict[str, Any]
    evidence_summary: EvidenceSummary
    truncated: bool
    total_tokens: int
    # Populated only when local retrieval was insufficient (Section 43) AND
    # Tavily was configured and returned results -- see
    # app.rag.pipeline.answer_query. Empty in every other case, including
    # every existing caller/test that never passes `web_sources` to
    # build_context_packet().
    web_sources: list[WebSourceEntry] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Render the required sections (Section 16) as LLM-ready text.

        EXTERNAL WEB SOURCES is deliberately its own section, after RETRIEVED
        SOURCES and before SAFETY RESULT, with explicit "unverified/external"
        language in both the header and every entry -- this is the
        structural half of "never presented with the same confidence as a
        reviewed medical guideline" (the other half is the fixed
        evidence_level/source_type on WebSourceEntry itself, which citation
        rendering and post-checks key off of).
        """
        context_lines = "\n".join(f"- {k}: {v}" for k, v in self.user_context.items() if v)
        sources_lines = "\n\n".join(
            f"[{s.chunk_id}] domain={s.domain} evidence_level={s.evidence_level} "
            f"review_status={s.review_status} source={s.source_id}\n{s.content}"
            for s in self.retrieved_sources
        )
        evidence_lines = (
            f"domains: {', '.join(self.evidence_summary.domains) or 'none'}\n"
            f"evidence_level_counts: {self.evidence_summary.evidence_level_counts}\n"
            f"needs_review: {self.evidence_summary.needs_review_chunk_ids or 'none'}"
        )
        sections = [
            f"USER CONTEXT\n{context_lines or '(none provided)'}",
            f"USER QUESTION\n{self.user_question}",
            f"RETRIEVED SOURCES\n{sources_lines or '(no sources retrieved)'}",
        ]
        if self.web_sources:
            web_lines = "\n\n".join(
                f"[{w.web_id}] EXTERNAL/UNVERIFIED WEB SOURCE (not part of the reviewed "
                f"local knowledge base) domain={w.domain} evidence_level={w.evidence_level} "
                f"url={w.url}\n{w.content}"
                for w in self.web_sources
            )
            sections.append(
                "EXTERNAL WEB SOURCES (UNVERIFIED -- from a live web search, not the "
                "reviewed local knowledge base; cite separately and never with the same "
                "confidence as RETRIEVED SOURCES)\n" + web_lines
            )
        sections.append(f"SAFETY RESULT\n{self.safety_result}")
        sections.append(f"EVIDENCE METADATA\n{evidence_lines}")
        return "\n\n".join(sections)


def build_context_packet(
    user_question: str,
    scored_chunks: list[tuple[KnowledgeChunk, float]],
    safety_result: dict[str, Any],
    user_context: UserContext | None = None,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    review_statuses: dict[str, str] | None = None,
    web_sources: list[WebSourceEntry] | None = None,
) -> ContextPacket:
    """Assemble the structured context packet. `scored_chunks` is assumed
    already ranked best-first (output of #7's rerank()); truncation drops
    the lowest-ranked chunks first when the token budget is exceeded.

    `KnowledgeChunk` (#1) doesn't carry `review_status` -- only the parent
    `KnowledgeDocument` does -- so `review_statuses` maps `document_id` to
    its document's review_status for chunks where that's known (same pattern
    as #7's `source_types` lookup for source quality).
    """
    review_statuses = review_statuses or {}
    user_context = user_context or UserContext()
    context_dict = {
        "pregnancy_stage": user_context.pregnancy_stage,
        "region": user_context.region,
        "context_terms": user_context.context_terms,
    }

    question_tokens = _token_count(user_question)
    running_tokens = question_tokens
    included: list[SourceEntry] = []
    truncated = False

    for chunk, _score in scored_chunks:
        chunk_tokens = _token_count(chunk.content)
        if included and running_tokens + chunk_tokens > max_tokens:
            # Stop entirely rather than skipping past this chunk to check
            # smaller ones further down the ranking -- scored_chunks is
            # best-first, so once one doesn't fit, every remaining chunk is
            # lower-ranked and must be dropped too, per this function's own
            # "drop lowest-ranked first" contract.
            truncated = True
            break
        running_tokens += chunk_tokens
        included.append(
            SourceEntry(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source_id=chunk.source_id,
                domain=chunk.domain,
                evidence_level=chunk.evidence_level,
                review_status=review_statuses.get(chunk.document_id),
                content=chunk.content,
            )
        )

    domains = sorted({s.domain for s in included})
    evidence_counts: dict[str, int] = {}
    for s in included:
        evidence_counts[s.evidence_level] = evidence_counts.get(s.evidence_level, 0) + 1
    needs_review = [
        s.chunk_id for s in included if s.review_status in _NEEDS_REVIEW_STATUSES
    ]

    return ContextPacket(
        user_context=context_dict,
        user_question=user_question,
        retrieved_sources=included,
        safety_result=safety_result,
        evidence_summary=EvidenceSummary(
            domains=domains,
            evidence_level_counts=evidence_counts,
            needs_review_chunk_ids=needs_review,
        ),
        truncated=truncated,
        total_tokens=running_tokens,
        web_sources=list(web_sources or []),
    )
