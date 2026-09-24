"""Full pipeline orchestration (issue #20, Master Prompt Section 12).

The first place all of #6-#19's individual pieces are actually wired
together into one call. Until now each piece (retrieval, reranking, context
packet, generation, citation validation, post-check, grounding, multi-domain
segmentation) had only been unit-tested or exercised individually inside the
various evaluation harnesses -- nothing verified they compose correctly as
one connected flow.

Order matches Section 12's RAG pipeline steps: safety pre-check (Step 4) ->
query rewriting/domain detection (Step 5) -> hybrid retrieval (Step 6) ->
reranking (Step 7) -> context construction (Step 8) -> grounding check
(Section 43) -> LLM generation (Step 9) -> citation validation (Step 11) ->
safety post-check (Section 21) -> final response (Step 12).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.evidence.citation_validation import (
    CitationValidationResult,
    validate_citations_against_packet,
)
from app.llm.groq_client import Groq, generate_from_packet
from app.rag.context_packet import ContextPacket, build_context_packet
from app.rag.grounding import INSUFFICIENT_EVIDENCE_RESPONSE, has_sufficient_evidence
from app.rag.multi_domain import multi_domain_retrieval_filter
from app.rag.reranking import UserContext, rerank
from app.rag.retrieval import hybrid_retrieve
from app.safety.classifier import SafetyClassification, classify
from app.safety.post_check import PostCheckReport, validate_and_finalize
from app.schemas.knowledge import KnowledgeChunk

DEFAULT_K = 5


@dataclass
class PipelineResult:
    query: str
    safety_result: SafetyClassification
    short_circuited: bool
    answer: str
    context_packet: ContextPacket | None = None
    citation_result: CitationValidationResult | None = None
    post_check_report: PostCheckReport | None = None


def answer_query(
    query: str,
    *,
    candidate_chunks: list[KnowledgeChunk],
    profile: UserContext | None = None,
    client: Groq | None = None,
    k: int = DEFAULT_K,
) -> PipelineResult:
    """Run the full pipeline for one query. `client` is injectable so this
    is testable without a live Groq key (same pattern as #9's
    generate_from_packet)."""
    safety_result = classify(query)
    safety_result_dict = {
        "risk_category": safety_result.risk_category,
        "matched_phrases": safety_result.matched_phrases,
        "message": safety_result.message,
    }

    # Section 20: safety rules always take priority -- short-circuit before
    # retrieval/generation ever runs.
    if safety_result.requires_short_circuit:
        return PipelineResult(
            query=query,
            safety_result=safety_result,
            short_circuited=True,
            answer=safety_result.message or "",
        )

    domains = multi_domain_retrieval_filter(query)
    retrieval = hybrid_retrieve(query, candidate_chunks=candidate_chunks, domains=domains, k=k)

    # Sufficiency must be checked against RAW retrieval scores, not
    # reranked ones: rerank() adds a constant baseline (evidence-level
    # weight, source quality) to every candidate regardless of actual query
    # relevance, so a reranked score is never exactly 0 even for a
    # completely unrelated query -- checking sufficiency post-rerank would
    # make the Section 43 grounding gate never trigger at all.
    if not has_sufficient_evidence(retrieval.chunks):
        packet = build_context_packet(query, [], safety_result=safety_result_dict)
        return PipelineResult(
            query=query,
            safety_result=safety_result,
            short_circuited=False,
            answer=INSUFFICIENT_EVIDENCE_RESPONSE,
            context_packet=packet,
        )

    reranked = rerank(retrieval.chunks, profile)
    packet = build_context_packet(query, reranked, safety_result=safety_result_dict)

    raw_answer = generate_from_packet(packet, client=client)
    citation_result = validate_citations_against_packet(raw_answer, packet)
    final_answer, post_check_report = validate_and_finalize(raw_answer, packet, safety_result)

    return PipelineResult(
        query=query,
        safety_result=safety_result,
        short_circuited=False,
        answer=final_answer,
        context_packet=packet,
        citation_result=citation_result,
        post_check_report=post_check_report,
    )
