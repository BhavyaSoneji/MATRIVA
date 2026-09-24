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

    def to_prompt_text(self) -> str:
        """Render the 5 required sections (Section 16) as LLM-ready text."""
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
        return (
            "USER CONTEXT\n"
            f"{context_lines or '(none provided)'}\n\n"
            "USER QUESTION\n"
            f"{self.user_question}\n\n"
            "RETRIEVED SOURCES\n"
            f"{sources_lines or '(no sources retrieved)'}\n\n"
            "SAFETY RESULT\n"
            f"{self.safety_result}\n\n"
            "EVIDENCE METADATA\n"
            f"{evidence_lines}"
        )


def build_context_packet(
    user_question: str,
    scored_chunks: list[tuple[KnowledgeChunk, float]],
    safety_result: dict[str, Any],
    user_context: UserContext | None = None,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    review_statuses: dict[str, str] | None = None,
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
    )
