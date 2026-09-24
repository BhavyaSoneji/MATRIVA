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

from sqlalchemy.orm import Session as DatabaseSession

from app.core.config import get_settings
from app.evidence.citation_validation import (
    CitationValidationResult,
    validate_citations_against_packet,
)
from app.llm.generator import GenerationResult, generate_grounded_answer
from app.llm.groq_client import Groq, generate_from_packet
from app.rag.context_packet import ContextPacket, build_context_packet
from app.rag.grounding import INSUFFICIENT_EVIDENCE_RESPONSE, has_sufficient_evidence
from app.rag.multi_domain import (
    multi_domain_retrieval_filter,
    requires_segmentation,
    validate_segmentation,
)
from app.rag.reranking import UserContext, rerank
from app.rag.retrieval import RetrievedChunk, hybrid_retrieve, retrieve_chunks
from app.safety.classifier import SafetyClassification, classify
from app.safety.post_check import (
    SAFE_FALLBACK_RESPONSE,
    PostCheckReport,
    validate_and_finalize,
)
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk, SourceType

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
    candidate_scores: dict[str, float] | None = None,
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
    retrieval = hybrid_retrieve(
        query,
        candidate_chunks=candidate_chunks,
        candidate_scores=candidate_scores,
        domains=domains,
        k=k,
    )

    # Sufficiency must be checked against RAW retrieval scores, not
    # reranked ones: rerank() adds a constant baseline (evidence-level
    # weight, source quality) to every candidate regardless of actual query
    # relevance, so a reranked score is never exactly 0 even for a
    # completely unrelated query -- checking sufficiency post-rerank would
    # make the Section 43 grounding gate never trigger at all.
    if not has_sufficient_evidence(retrieval.chunks, scoring_mode=retrieval.scoring_mode):
        packet = build_context_packet(query, [], safety_result=safety_result_dict)
        return PipelineResult(
            query=query,
            safety_result=safety_result,
            short_circuited=False,
            answer=INSUFFICIENT_EVIDENCE_RESPONSE,
            context_packet=packet,
        )

    reranked = rerank(retrieval.chunks, profile)
    packet = build_context_packet(
        query, reranked, safety_result=safety_result_dict, user_context=profile
    )

    raw_answer = generate_from_packet(packet, client=client)

    # Section 31: if the retrieved evidence spans AYURVEDA + another domain,
    # the response MUST actually separate MODERN/TRADITIONAL/EVIDENCE STATUS
    # sections -- groq_client only asks the LLM to do this via a prompt
    # addendum, so this is the check that verifies compliance rather than
    # trusting the model. Fail closed, same as every other check here.
    if requires_segmentation(packet.evidence_summary.domains) and not validate_segmentation(
        raw_answer
    ).is_segmented:
        return PipelineResult(
            query=query,
            safety_result=safety_result,
            short_circuited=False,
            answer=SAFE_FALLBACK_RESPONSE,
            context_packet=packet,
        )

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


# --- Database/API adapter -------------------------------------------------
# The API uses SQLAlchemy models for persistence, while the RAG team's pipeline
# uses the Pydantic knowledge schema.  Keep that boundary explicit so either
# side can evolve without making the HTTP layer depend on ORM internals.
_DOMAIN_MAP = {
    "modern_medical": Domain.MODERN_MEDICAL,
    "ayurveda": Domain.AYURVEDA,
    "nutrition": Domain.NUTRITION,
    "lifestyle": Domain.LIFESTYLE,
    "regional_cultural": Domain.REGIONAL_CULTURAL,
    "antenatal_care": Domain.MODERN_MEDICAL,
}
_SOURCE_TYPE_MAP = {
    "government": SourceType.INSTITUTIONAL_GUIDANCE,
    "professional_society": SourceType.MEDICAL_GUIDELINE,
    "international": SourceType.INSTITUTIONAL_GUIDANCE,
    "academic": SourceType.CLINICAL_REFERENCE,
    "traditional": SourceType.TRADITIONAL_REFERENCE,
    "internal": SourceType.CLINICAL_REFERENCE,
}
_EVIDENCE_MAP = {
    "traditional": EvidenceLevel.TRADITIONAL,
    "preliminary": EvidenceLevel.PRELIMINARY,
    "limited_evidence": EvidenceLevel.LIMITED_EVIDENCE,
    "mixed_evidence": EvidenceLevel.MIXED_EVIDENCE,
    "supported": EvidenceLevel.SUPPORTED,
    "uncertain": EvidenceLevel.UNCERTAIN,
    "not_established": EvidenceLevel.NOT_ESTABLISHED,
}


def _as_rag_chunk(item: RetrievedChunk) -> KnowledgeChunk:
    document = item.document
    source = item.source
    return KnowledgeChunk(
        chunk_id=item.chunk.id,
        document_id=document.id,
        source_id=source.id,
        domain=_DOMAIN_MAP.get((document.domain or "").lower(), Domain.MODERN_MEDICAL),
        topic=source.topic,
        pregnancy_stage=document.pregnancy_stage,
        evidence_level=_EVIDENCE_MAP.get((source.evidence_level or "").lower(), EvidenceLevel.UNCERTAIN),
        region=document.region,
        language=document.language or "en",
        content=item.chunk.content,
        chunk_index=item.chunk.chunk_index,
        token_count=len(item.chunk.content.split()),
    )


def answer_question(
    db: DatabaseSession,
    query: str,
    *,
    domain: str | None = None,
    stage: str | None = None,
    region: str | None = None,
) -> tuple[GenerationResult, list[RetrievedChunk]]:
    """Run the full RAG pipeline when a provider key is configured.

    The no-key path remains deterministic and source-grounded for local/demo use.  It is
    deliberately not treated as a live clinical model result.
    """

    retrieved = retrieve_chunks(db, query, domain=domain, stage=stage, region=region)
    if not retrieved:
        return GenerationResult(text="", citation_ids=[]), retrieved

    settings = get_settings()
    if settings.llm_api_key:
        try:
            profile = UserContext(pregnancy_stage=stage, region=region)
            rag_chunks = [_as_rag_chunk(item) for item in retrieved]
            result = answer_query(
                query,
                candidate_chunks=rag_chunks,
                candidate_scores={chunk.chunk_id: item.score for chunk, item in zip(rag_chunks, retrieved)},
                profile=profile,
            )
            return GenerationResult(
                text=result.answer,
                citation_ids=list(dict.fromkeys(item.source.id for item in retrieved)),
                used_external_provider=True,
            ), retrieved
        except Exception:  # noqa: BLE001, S110
            # Provider/pipeline failures must not bypass the safe local fallback.
            pass

    return generate_grounded_answer(query, retrieved), retrieved
