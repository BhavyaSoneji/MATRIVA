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

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from sqlalchemy.orm import Session as DatabaseSession

from app.core.config import Settings, get_settings
from app.evidence.citation_validation import (
    CitationValidationResult,
    validate_citations_against_packet,
)
from app.llm.generator import GenerationResult, generate_grounded_answer
from app.llm.groq_client import Groq, generate_from_packet, stream_from_packet
from app.llm.langchain_provider import build_generation_runnable, stream_generation
from app.rag.context_packet import ContextPacket, WebSourceEntry, build_context_packet
from app.rag.grounding import INSUFFICIENT_EVIDENCE_RESPONSE, has_sufficient_evidence
from app.rag.multi_domain import (
    multi_domain_retrieval_filter,
    requires_segmentation,
    validate_segmentation,
)
from app.rag.reranking import UserContext, rerank
from app.rag.retrieval import RetrievedChunk, hybrid_retrieve, retrieve_chunks_scored
from app.rag.web_search import search_web
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
    used_web_search: bool = False


@dataclass
class GenerationPlan:
    """Output of `_prepare_generation`: either the pipeline is already done
    (short-circuit or insufficient evidence, `early_result` set, no LLM call
    needed at all) or generation may proceed against `context_packet`.

    Splitting `answer_query`'s "everything up to the LLM call" from "the LLM
    call and what happens after" is what lets `answer_query_stream` reuse
    every single safety/retrieval/grounding/web-search decision `answer_query`
    makes, changing only how the LLM is actually invoked (blocking vs
    streamed tokens) -- see module docstring update.
    """

    early_result: PipelineResult | None
    context_packet: ContextPacket | None = None
    safety_result: SafetyClassification | None = None


@dataclass
class StreamEvent:
    """One event yielded by `answer_query_stream`.

    kind="delta": `text` is the next chunk of raw LLM output as it arrives
    (or, for an early/short-circuited result, the ENTIRE answer text sent as
    a single delta -- there is no LLM to stream tokens from in that case).
    kind="final": generation (or the short-circuit) is complete; `result` is
    the same `PipelineResult` shape `answer_query` would have returned for
    this query, already run through citation validation and the safety
    post-check. `text` mirrors `result.answer` for convenience.

    `result.answer` can differ from the concatenation of every prior
    "delta" `text` -- that's not a bug, it's Section 21's post-check
    replacing an unsafe/invalid raw answer with SAFE_FALLBACK_RESPONSE (or
    Section 31's segmentation check doing the same). Callers MUST treat the
    final event's text as authoritative and replace anything shown from
    deltas, not merge them.
    """

    kind: str  # "delta" | "final"
    text: str
    result: PipelineResult | None = None


def _prepare_generation(
    query: str,
    *,
    candidate_chunks: list[KnowledgeChunk],
    candidate_scores: dict[str, float] | None = None,
    candidate_scoring_mode: str | None = None,
    profile: UserContext | None = None,
    k: int = DEFAULT_K,
) -> GenerationPlan:
    """Everything `answer_query` does BEFORE the LLM call: safety pre-check
    (and its short-circuit), hybrid retrieval, the Section 43 grounding gate
    (including the Tavily web-search fallback), reranking, and context
    packet construction. Shared verbatim by the blocking and streaming
    entry points so neither can silently diverge on safety or retrieval
    behavior."""
    safety_result = classify(query)
    safety_result_dict = {
        "risk_category": safety_result.risk_category,
        "matched_phrases": safety_result.matched_phrases,
        "message": safety_result.message,
    }

    # Section 20: safety rules always take priority -- short-circuit before
    # retrieval/generation (or web search) ever runs.
    if safety_result.requires_short_circuit:
        return GenerationPlan(
            early_result=PipelineResult(
                query=query,
                safety_result=safety_result,
                short_circuited=True,
                answer=safety_result.message or "",
            )
        )

    domains = multi_domain_retrieval_filter(query)
    retrieval = hybrid_retrieve(
        query,
        candidate_chunks=candidate_chunks,
        candidate_scores=candidate_scores,
        candidate_scoring_mode=candidate_scoring_mode,
        domains=domains,
        k=k,
    )

    # Sufficiency must be checked against RAW retrieval scores, not
    # reranked ones: rerank() adds a constant baseline (evidence-level
    # weight, source quality) to every candidate regardless of actual query
    # relevance, so a reranked score is never exactly 0 even for a
    # completely unrelated query -- checking sufficiency post-rerank would
    # make the Section 43 grounding gate never trigger at all.
    web_sources: list[WebSourceEntry] = []
    if not has_sufficient_evidence(retrieval.chunks, scoring_mode=retrieval.scoring_mode):
        # Section 43's gate has fired on the local corpus. Before falling
        # back to the fixed insufficient-evidence response, try ONE more
        # source of evidence -- but only if an operator has actually
        # configured Tavily; with no key this branch is a no-op and behavior
        # is byte-for-byte identical to before this feature existed.
        settings = get_settings()
        if settings.tavily_api_key:
            web_results = search_web(query, api_key=settings.tavily_api_key)
            web_sources = [
                WebSourceEntry(
                    web_id=f"web{index}",
                    title=result.title,
                    url=result.url,
                    domain=result.domain,
                    content=result.content,
                )
                for index, result in enumerate(web_results, start=1)
            ]
        if not web_sources:
            packet = build_context_packet(query, [], safety_result=safety_result_dict)
            return GenerationPlan(
                early_result=PipelineResult(
                    query=query,
                    safety_result=safety_result,
                    short_circuited=False,
                    answer=INSUFFICIENT_EVIDENCE_RESPONSE,
                    context_packet=packet,
                )
            )

    # Local chunks are still included (clearly separated) alongside web
    # results when both are present -- web search supplements the local
    # corpus here, it doesn't replace whatever local evidence does exist.
    reranked = rerank(retrieval.chunks, profile)
    packet = build_context_packet(
        query,
        reranked,
        safety_result=safety_result_dict,
        user_context=profile,
        web_sources=web_sources or None,
    )
    return GenerationPlan(early_result=None, context_packet=packet, safety_result=safety_result)


def _finalize_generation(
    query: str,
    raw_answer: str,
    packet: ContextPacket,
    safety_result: SafetyClassification,
    *,
    used_web_search: bool,
) -> PipelineResult:
    """Everything `answer_query` does AFTER the LLM call: Section 31's
    multi-domain segmentation check, citation validation, and the Section 21
    safety post-check. Shared verbatim by the blocking and streaming entry
    points -- a streamed answer gets exactly the same scrutiny a blocking one
    does, just applied to the fully-buffered text once streaming completes."""
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
        used_web_search=used_web_search,
    )


def _langchain_answer_query(
    query: str,
    *,
    candidate_chunks: list[KnowledgeChunk],
    candidate_scores: dict[str, float] | None,
    candidate_scoring_mode: str | None,
    profile: UserContext | None,
    client: Groq | None,
    k: int,
    settings: Settings,
) -> PipelineResult:
    """Compose the complete blocking RAG path as a LangChain runnable chain.

    The independent safety, grounding, citation and post-check functions are
    unchanged. LangChain owns orchestration and provider invocation, so a
    safety short-circuit never reaches retrieval/generation and every completed
    answer still passes the same fail-closed finalization path.
    """

    generation = build_generation_runnable(
        settings=settings,
        client=client,
        legacy_generator=generate_from_packet,
    )

    def prepare(_: None) -> dict[str, GenerationPlan]:
        plan = _prepare_generation(
            query,
            candidate_chunks=candidate_chunks,
            candidate_scores=candidate_scores,
            candidate_scoring_mode=candidate_scoring_mode,
            profile=profile,
            k=k,
        )
        return {"plan": plan}

    def has_early_result(state: dict[str, GenerationPlan]) -> bool:
        return state["plan"].early_result is not None

    def early_result(state: dict[str, GenerationPlan]) -> PipelineResult:
        result = state["plan"].early_result
        assert result is not None
        return result

    def context_packet(state: dict[str, GenerationPlan]) -> ContextPacket:
        packet = state["plan"].context_packet
        assert packet is not None
        return packet

    def finalize(state: dict[str, Any]) -> PipelineResult:
        plan = state["plan"]
        packet = state["context_packet"]
        safety = plan.safety_result
        assert packet is not None and safety is not None
        return _finalize_generation(
            query,
            str(state["raw_answer"]),
            packet,
            safety,
            used_web_search=bool(packet.web_sources),
        )

    prepare_step = RunnableLambda(prepare)
    assign_packet = RunnablePassthrough.assign(context_packet=context_packet)
    generate_step = RunnablePassthrough.assign(
        raw_answer=(RunnableLambda(context_packet) | generation)
    )
    branch = RunnableBranch(
        (has_early_result, RunnableLambda(early_result)),
        (assign_packet | generate_step | RunnableLambda(finalize)),
    )
    return (prepare_step | branch).invoke(None)


def answer_query(
    query: str,
    *,
    candidate_chunks: list[KnowledgeChunk],
    candidate_scores: dict[str, float] | None = None,
    candidate_scoring_mode: str | None = None,
    profile: UserContext | None = None,
    client: Groq | None = None,
    k: int = DEFAULT_K,
) -> PipelineResult:
    """Run the full pipeline for one query.

    Production orchestration uses LangChain runnables. ``RAG_ORCHESTRATOR=native``
    keeps the original explicit Python sequence as a compatibility/rollback
    seam. An injected Groq-compatible client remains supported in both modes
    for deterministic tests without a live provider key.
    """

    settings = get_settings()
    if getattr(settings, "rag_orchestrator", "native") == "langchain":
        return _langchain_answer_query(
            query,
            candidate_chunks=candidate_chunks,
            candidate_scores=candidate_scores,
            candidate_scoring_mode=candidate_scoring_mode,
            profile=profile,
            client=client,
            k=k,
            settings=settings,
        )

    plan = _prepare_generation(
        query,
        candidate_chunks=candidate_chunks,
        candidate_scores=candidate_scores,
        candidate_scoring_mode=candidate_scoring_mode,
        profile=profile,
        k=k,
    )
    if plan.early_result is not None:
        return plan.early_result
    assert plan.context_packet is not None and plan.safety_result is not None

    raw_answer = generate_from_packet(plan.context_packet, client=client)
    return _finalize_generation(
        query,
        raw_answer,
        plan.context_packet,
        plan.safety_result,
        used_web_search=bool(plan.context_packet.web_sources),
    )


def answer_query_stream(
    query: str,
    *,
    candidate_chunks: list[KnowledgeChunk],
    candidate_scores: dict[str, float] | None = None,
    candidate_scoring_mode: str | None = None,
    profile: UserContext | None = None,
    client: Groq | None = None,
    k: int = DEFAULT_K,
) -> Iterator[StreamEvent]:
    """Streaming counterpart to `answer_query`, for POST /chat/stream.

    Reuses `_prepare_generation` and `_finalize_generation` verbatim -- the
    ONLY thing that differs from `answer_query` is that the LLM call itself
    (`stream_from_packet` instead of `generate_from_packet`) yields tokens as
    they arrive. Safety pre-check, retrieval, the Section 43 grounding gate
    (including web search), Section 31 segmentation, citation validation,
    and the Section 21 safety post-check all still run, unchanged, against
    the fully-buffered text once the stream completes -- see module
    docstring and `StreamEvent`.

    If a short-circuit or insufficient-evidence result is produced by
    `_prepare_generation`, the LLM is never called at all (same as
    `answer_query`) -- the fixed answer is yielded as a single "delta" event
    immediately followed by "final", so callers can treat every query
    uniformly as a stream of deltas terminated by one final event.

    If the Groq stream itself fails partway through (network drop, API
    error), whatever partial text was already yielded as "delta" events
    cannot be un-sent -- so this never trusts that partial text: it discards
    it and yields a "final" event with SAFE_FALLBACK_RESPONSE, the same safe
    behavior a post-check failure produces. Callers MUST replace whatever
    was rendered from prior deltas with the final event's text, never merge.
    """
    settings = get_settings()
    use_langchain = getattr(settings, "rag_orchestrator", "native") == "langchain"
    plan = _prepare_generation(
        query,
        candidate_chunks=candidate_chunks,
        candidate_scores=candidate_scores,
        candidate_scoring_mode=candidate_scoring_mode,
        profile=profile,
        k=k,
    )
    if plan.early_result is not None:
        yield StreamEvent(kind="delta", text=plan.early_result.answer)
        yield StreamEvent(kind="final", text=plan.early_result.answer, result=plan.early_result)
        return
    assert plan.context_packet is not None and plan.safety_result is not None

    buffer: list[str] = []
    try:
        if use_langchain:
            deltas = stream_generation(
                plan.context_packet,
                settings=settings,
                client=client,
                legacy_streamer=stream_from_packet,
            )
        else:
            deltas = stream_from_packet(plan.context_packet, client=client)
        for delta in deltas:
            buffer.append(delta)
            yield StreamEvent(kind="delta", text=delta)
    except Exception:  # noqa: BLE001
        # A partially-streamed, un-validated answer must never be presented
        # as final -- see docstring. `_finalize_generation` is not called at
        # all here since there's no complete raw_answer to run it against.
        result = PipelineResult(
            query=query,
            safety_result=plan.safety_result,
            short_circuited=False,
            answer=SAFE_FALLBACK_RESPONSE,
            context_packet=plan.context_packet,
        )
        yield StreamEvent(kind="final", text=result.answer, result=result)
        return

    raw_answer = "".join(buffer)
    result = _finalize_generation(
        query,
        raw_answer,
        plan.context_packet,
        plan.safety_result,
        used_web_search=bool(plan.context_packet.web_sources),
    )
    yield StreamEvent(kind="final", text=result.answer, result=result)


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
    profile: UserContext | None = None,
) -> tuple[GenerationResult, list[RetrievedChunk]]:
    """Run the full RAG pipeline when a provider key is configured.

    The no-key path remains deterministic and source-grounded for local/demo use.  It is
    deliberately not treated as a live clinical model result.
    """

    settings = get_settings()
    if settings.rag_engine == "local":
        # Offline pipeline: no LLM, no embedding API, no web search (app/rag/local).
        from app.rag.local.engine import answer_local

        return answer_local(db, query, stage=stage, region=region, profile=profile)

    retrieved, scoring_mode = retrieve_chunks_scored(db, query, domain=domain, stage=stage, region=region)
    # Normally zero local retrieval means an immediate, deterministic
    # "no evidence" result -- but when both Groq and Tavily are configured,
    # answer_query() below still has a shot at grounding the answer in a
    # live web search once its own Section 43 gate sees zero/insufficient
    # local evidence, so it's worth letting the full pipeline run instead of
    # short-circuiting here. With no Tavily key (the default, and the only
    # configuration this environment can actually exercise) this condition
    # reduces to exactly the original `if not retrieved: return` check.
    if not retrieved and not (settings.llm_api_key and settings.tavily_api_key):
        return GenerationResult(text="", citation_ids=[]), retrieved

    if settings.llm_api_key:
        try:
            profile = profile or UserContext(pregnancy_stage=stage, region=region)
            rag_chunks = [_as_rag_chunk(item) for item in retrieved]
            result = answer_query(
                query,
                candidate_chunks=rag_chunks,
                candidate_scores={chunk.chunk_id: item.score for chunk, item in zip(rag_chunks, retrieved)},
                candidate_scoring_mode=scoring_mode,
                profile=profile,
            )
            web_citations = list(result.context_packet.web_sources) if result.context_packet else []
            if not retrieved and not web_citations:
                # The full pipeline ran (Tavily was configured) but web
                # search itself returned nothing usable -- fall through to
                # the exact same "no evidence at all" result the no-key path
                # would have produced, rather than returning `result.answer`
                # (which is INSUFFICIENT_EVIDENCE_RESPONSE here anyway, but
                # going through this shared path keeps behavior consistent).
                return GenerationResult(text="", citation_ids=[]), retrieved
            return GenerationResult(
                text=result.answer,
                citation_ids=list(dict.fromkeys(item.source.id for item in retrieved)),
                used_external_provider=True,
                web_citations=web_citations,
            ), retrieved
        except Exception:  # noqa: BLE001, S110
            # Provider/pipeline failures must not bypass the safe local fallback.
            pass

    if not retrieved:
        return GenerationResult(text="", citation_ids=[]), retrieved
    return generate_grounded_answer(query, retrieved), retrieved


@dataclass
class ChatStreamEvent:
    """DB-adapter-level counterpart to `StreamEvent`, for POST /chat/stream
    (see app.services.chat.stream_chat). Shaped around `GenerationResult`
    (the same type `answer_question` returns) rather than `PipelineResult`,
    since that's what the API/service layer already knows how to turn into
    citations/sources.

    kind="delta": `text` is the next chunk of raw LLM output.
    kind="final": generation is complete; `generation`/`chunks` are exactly
    what `answer_question` would have returned for this query -- callers run
    the SAME post-processing (app.safety.classifier.validate_generated_answer
    etc.) against them that the non-streaming /chat endpoint does.
    """

    kind: str  # "delta" | "final"
    text: str
    generation: GenerationResult | None = None
    chunks: list[RetrievedChunk] = field(default_factory=list)


def answer_question_stream(
    db: DatabaseSession,
    query: str,
    *,
    domain: str | None = None,
    stage: str | None = None,
    region: str | None = None,
    profile: UserContext | None = None,
) -> Iterator[ChatStreamEvent]:
    """Streaming counterpart to `answer_question`, for POST /chat/stream.

    Mirrors `answer_question`'s exact branching (no-key local fallback,
    zero-local-evidence short circuit, Tavily-augmented full pipeline,
    provider-failure fallback) so a caller gets the same final answer either
    endpoint would have produced for the same input -- the only path that
    actually streams token-by-token is the Groq-backed one, via
    `answer_query_stream`. The no-key local-grounded path and the
    zero-evidence path have nothing to stream (there is no live model call
    to stream from), so they're emitted as a single "delta" + "final" pair,
    exactly like `answer_query_stream` does for its own short-circuit case.
    """
    settings = get_settings()
    if settings.rag_engine == "local":
        from app.rag.local.engine import answer_local, stream_pieces

        generation, chunks = answer_local(db, query, stage=stage, region=region, profile=profile)
        for piece in stream_pieces(generation.text) if generation.text else ():
            yield ChatStreamEvent(kind="delta", text=piece)
        yield ChatStreamEvent(kind="final", text=generation.text, generation=generation, chunks=chunks)
        return

    retrieved, scoring_mode = retrieve_chunks_scored(db, query, domain=domain, stage=stage, region=region)

    if not settings.llm_api_key:
        # No live model configured at all -- reuse the exact non-streaming
        # local-grounded/no-evidence result and emit it as one event; there
        # is nothing to stream token-by-token without Groq.
        generation, chunks = answer_question(db, query, domain=domain, stage=stage, region=region, profile=profile)
        yield ChatStreamEvent(kind="delta", text=generation.text)
        yield ChatStreamEvent(kind="final", text=generation.text, generation=generation, chunks=chunks)
        return

    if not retrieved and not settings.tavily_api_key:
        generation = GenerationResult(text="", citation_ids=[])
        yield ChatStreamEvent(kind="final", text="", generation=generation, chunks=retrieved)
        return

    profile = profile or UserContext(pregnancy_stage=stage, region=region)
    rag_chunks = [_as_rag_chunk(item) for item in retrieved]
    try:
        for event in answer_query_stream(
            query,
            candidate_chunks=rag_chunks,
            candidate_scores={chunk.chunk_id: item.score for chunk, item in zip(rag_chunks, retrieved)},
            candidate_scoring_mode=scoring_mode,
            profile=profile,
        ):
            if event.kind == "delta":
                yield ChatStreamEvent(kind="delta", text=event.text)
                continue
            result = event.result
            web_citations = list(result.context_packet.web_sources) if result and result.context_packet else []
            if not retrieved and not web_citations:
                # Same "web search ran but found nothing" fallback
                # `answer_question` applies -- keep the two paths consistent.
                generation = GenerationResult(text="", citation_ids=[])
            else:
                generation = GenerationResult(
                    text=event.text,
                    citation_ids=list(dict.fromkeys(item.source.id for item in retrieved)),
                    used_external_provider=True,
                    web_citations=web_citations,
                )
            yield ChatStreamEvent(kind="final", text=generation.text, generation=generation, chunks=retrieved)
    except Exception:  # noqa: BLE001
        # Provider/pipeline failures must not bypass the safe local
        # fallback -- same contract as answer_question's try/except, just
        # emitted as a single final event since nothing was validly
        # streamed. Any "delta" events already yielded above are exactly
        # the raw (unvalidated) tokens the caller must discard/replace, same
        # as a mid-stream Groq failure inside answer_query_stream.
        generation = generate_grounded_answer(query, retrieved) if retrieved else GenerationResult(text="", citation_ids=[])
        yield ChatStreamEvent(kind="final", text=generation.text, generation=generation, chunks=retrieved)
