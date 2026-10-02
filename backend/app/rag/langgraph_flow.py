"""LangGraph orchestration for the MATRIVA query-to-response path (issue #116).

This is a structural alternative to the linear LangChain LCEL chain in
``app.rag.pipeline._langchain_answer_query``. It runs the *same* stages with the
*same* functions -- only the control flow is expressed as an explicit graph:

    START -> prepare -> (short-circuit? -> END)
                          -> generate -> finalize -> END

Why bother when LCEL already works:

- Every stage is an individually named, individually testable node.
- The routing decision is a real edge rather than an implicit branch, so the
  executed path can be traced and asserted.
- The shape maps one-to-one onto the pipeline described in ``docs/rag.md``,
  which makes safety review (see ``docs/safety.md``) auditable against the code.

Deliberately *not* changed:

- The safety pre-check, grounding gate, segmentation check, citation
  validation and safety post-check are the same imported functions used by the
  native and LCEL paths. LangGraph routes between them; it never relaxes them.
- ``_prepare_generation`` and ``_finalize_generation`` are reused verbatim, so
  blocking and streaming cannot drift apart, and no stage can be skipped by
  accident in this graph because it is not written here at all.
- The provider is built lazily inside the ``generate`` node, so a short-circuit
  never constructs an LLM client. This mirrors the LCEL behaviour and is
  asserted in ``tests/test_langgraph_flow.py``.

Select it with ``RAG_ORCHESTRATOR=langgraph``; ``langchain`` (default) and
``native`` remain available.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings
from app.llm.groq_client import Groq, generate_from_packet
from app.llm.langchain_provider import build_generation_runnable, stream_generation
from app.rag.context_packet import ContextPacket
from app.rag.pipeline import (
    DEFAULT_K,
    GenerationPlan,
    PipelineResult,
    StreamEvent,
    _finalize_generation,
    _prepare_generation,
)
from app.rag.reranking import UserContext
from app.schemas.knowledge import KnowledgeChunk


class LangGraphState(TypedDict, total=False):
    """Mutable state threaded through the graph.

    ``total=False`` so a node can return just the keys it changed; LangGraph
    merges the partial update into the accumulated state.

    ``request`` is the immutable per-call input (see ``GraphRequest``). It is
    set once at invoke time and never written by a node, which lets the compiled
    graph be reused across queries.
    """

    request: GraphRequest
    plan: GenerationPlan
    raw_answer: str
    result: PipelineResult


def build_graph(settings: Settings, client: Groq | None = None) -> Any:
    """Compile the LangGraph state graph for the blocking query path.

    Returned type is ``CompiledStateGraph``; annotated loosely so the module
    does not depend on LangGraph's generic parameterisation internals.
    """

    # The generation runnable is *created* here but the provider client is only
    # *constructed* when the generate node actually runs (see build_generation_
    # runnable's lazy model), which is what keeps a short-circuit off the
    # provider path entirely.
    generation = build_generation_runnable(
        settings=settings,
        client=client,
        legacy_generator=generate_from_packet,
    )

    def prepare(state: LangGraphState) -> LangGraphState:
        """Safety pre-check, retrieval, grounding gate, context packet.

        Returns a plan whose ``early_result`` is set when the pipeline is
        already complete (urgent query, or insufficient evidence) and no LLM
        call is needed at all.
        """

        config = state.get("request")
        assert isinstance(config, GraphRequest)
        plan = _prepare_generation(
            config.query,
            candidate_chunks=config.candidate_chunks,
            candidate_scores=config.candidate_scores,
            candidate_scoring_mode=config.candidate_scoring_mode,
            profile=config.profile,
            k=config.k,
        )
        return {"plan": plan}

    def route_after_prepare(state: LangGraphState) -> str:
        """Short-circuit before any generation work when the plan is done."""

        plan = state.get("plan")
        return "complete" if plan is not None and plan.early_result is not None else "generate"

    def complete(state: LangGraphState) -> LangGraphState:
        """Terminal node for a short-circuit / insufficient-evidence result."""

        plan = state.get("plan")
        assert plan is not None and plan.early_result is not None
        return {"result": plan.early_result}

    def generate(state: LangGraphState) -> LangGraphState:
        """The only node that touches the LLM."""

        plan = state.get("plan")
        assert plan is not None and plan.context_packet is not None
        raw_answer = generation.invoke(plan.context_packet)
        return {"raw_answer": str(raw_answer)}

    def finalize(state: LangGraphState) -> LangGraphState:
        """Segmentation check, citation validation, fail-closed post-check."""

        config = state.get("request")
        plan = state.get("plan")
        assert isinstance(config, GraphRequest)
        assert plan is not None
        assert plan.context_packet is not None and plan.safety_result is not None
        packet: ContextPacket = plan.context_packet
        result = _finalize_generation(
            config.query,
            state.get("raw_answer", ""),
            packet,
            plan.safety_result,
            used_web_search=bool(packet.web_sources),
        )
        return {"result": result}

    graph = StateGraph(LangGraphState)
    graph.add_node("prepare", prepare)
    graph.add_node("complete", complete)
    graph.add_node("generate", generate)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "prepare")
    graph.add_conditional_edges(
        "prepare",
        route_after_prepare,
        {"complete": "complete", "generate": "generate"},
    )
    graph.add_edge("generate", "finalize")
    graph.add_edge("complete", END)
    graph.add_edge("finalize", END)
    return graph.compile()


@dataclass(frozen=True)
class GraphRequest:
    """Per-call inputs.

    Carried on the state as an opaque ``request`` key rather than flattened into
    the TypedDict, so ``build_graph`` can be compiled once and reused across
    queries instead of rebuilt per call.
    """

    query: str
    candidate_chunks: list[KnowledgeChunk]
    candidate_scores: dict[str, float] | None = None
    candidate_scoring_mode: str | None = None
    profile: UserContext | None = None
    k: int = DEFAULT_K


def answer_query_graph(
    query: str,
    *,
    settings: Settings,
    candidate_chunks: list[KnowledgeChunk],
    candidate_scores: dict[str, float] | None = None,
    candidate_scoring_mode: str | None = None,
    profile: UserContext | None = None,
    client: Groq | None = None,
    k: int = DEFAULT_K,
    graph: Any | None = None,
) -> PipelineResult:
    """Run one query through the LangGraph and return the same PipelineResult."""

    compiled = graph or build_graph(settings, client=client)
    request = GraphRequest(
        query=query,
        candidate_chunks=candidate_chunks,
        candidate_scores=candidate_scores,
        candidate_scoring_mode=candidate_scoring_mode,
        profile=profile,
        k=k,
    )
    final = compiled.invoke({"request": request})
    result = final.get("result")
    assert isinstance(result, PipelineResult)
    return result


def answer_query_graph_stream(
    query: str,
    *,
    settings: Settings,
    candidate_chunks: list[KnowledgeChunk],
    candidate_scores: dict[str, float] | None = None,
    candidate_scoring_mode: str | None = None,
    profile: UserContext | None = None,
    client: Groq | None = None,
    k: int = DEFAULT_K,
) -> Iterator[StreamEvent]:
    """Streaming counterpart, same node graph for prepare/finalize.

    The graph still decides routing and short-circuiting; only the generate
    node's output is streamed as deltas. The same fail-closed contract applies:
    a stream that dies part-way yields SAFE_FALLBACK_RESPONSE as the final
    event rather than trusting partial text.
    """

    from app.safety.post_check import SAFE_FALLBACK_RESPONSE

    request = GraphRequest(
        query=query,
        candidate_chunks=candidate_chunks,
        candidate_scores=candidate_scores,
        candidate_scoring_mode=candidate_scoring_mode,
        profile=profile,
        k=k,
    )

    # Run the real graph but halt at the "prepare" node, so the streaming path
    # shares the exact same preparation and routing decision the blocking graph
    # makes. Halting here (rather than reimplementing preparation locally) is
    # what keeps the two paths from drifting, and it guarantees the generate
    # node has not run -- so no tokens are generated twice.
    compiled = build_graph(settings, client=client)
    prepared = compiled.invoke({"request": request}, interrupt_after=["prepare"])

    plan: GenerationPlan | None = prepared.get("plan")
    if plan is None:
        # Defensive: the graph always runs "prepare" first.
        raise RuntimeError("LangGraph produced no prepare plan")

    if plan.early_result is not None:
        yield StreamEvent(kind="delta", text=plan.early_result.answer)
        yield StreamEvent(kind="final", text=plan.early_result.answer, result=plan.early_result)
        return

    assert plan.context_packet is not None and plan.safety_result is not None
    buffer: list[str] = []
    try:
        for delta in stream_generation(
            plan.context_packet,
            settings=settings,
            client=client,
        ):
            buffer.append(delta)
            yield StreamEvent(kind="delta", text=delta)
    except Exception:  # noqa: BLE001
        fallback = PipelineResult(
            query=query,
            safety_result=plan.safety_result,
            short_circuited=False,
            answer=SAFE_FALLBACK_RESPONSE,
            context_packet=plan.context_packet,
        )
        yield StreamEvent(kind="final", text=fallback.answer, result=fallback)
        return

    finalized = _finalize_generation(
        query,
        "".join(buffer),
        plan.context_packet,
        plan.safety_result,
        used_web_search=bool(plan.context_packet.web_sources),
    )
    yield StreamEvent(kind="final", text=finalized.answer, result=finalized)