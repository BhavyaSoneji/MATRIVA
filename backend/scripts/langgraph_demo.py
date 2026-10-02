"""Run one query through the LangGraph and print the response + node trace.

Issue #116. This is the "show me what LangGraph responds" harness: it exercises
the real graph (same safety, retrieval, grounding, citation and post-check code
as production) with a stubbed LLM, so it needs no API key and never contacts a
provider. The stub is clearly labelled in the output -- it is a control-flow
demo, not a quality claim.

Usage
-----
    cd backend
    python -m scripts.langgraph_demo "What should I eat in the first trimester?"

    # urgent / short-circuit route
    python -m scripts.langgraph_demo "I have heavy bleeding"

    # insufficient-evidence route
    python -m scripts.langgraph_demo --weak-evidence "What is the capital of France?"

    # stream the tokens as they arrive
    python -m scripts.langgraph_demo --stream "What should I eat in pregnancy?"

The stub answers by quoting the context packet's own retrieved passages and
citing their real source ids, so citation validation has something genuine to
check.
"""

from __future__ import annotations

import argparse
import sys
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.core.config import Settings, get_settings
from app.llm import langchain_provider
from app.rag import pipeline as pipeline_module
from app.rag.langgraph_flow import DEFAULT_K, GraphRequest, answer_query_graph, build_graph
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk, SourceType


def _request_for(
    query: str,
    chunk: KnowledgeChunk,
    scores: dict[str, float] | None = None,
) -> GraphRequest:
    return GraphRequest(
        query=query,
        candidate_chunks=[chunk],
        candidate_scores=scores,
        k=DEFAULT_K,
    )


def _demo_chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="chunk-demo-1",
        document_id="doc-demo-1",
        source_id="src-demo-nutrition",
        domain=Domain.NUTRITION,
        topic="pregnancy nutrition",
        evidence_level=EvidenceLevel.SUPPORTED,
        source_type=SourceType.NUTRITION_REFERENCE,
        language="en",
        content=(
            "During pregnancy, eat a balanced diet that includes iron-rich foods "
            "such as lentils, spinach and jaggery, along with protein, fruit and "
            "vegetables. Avoid empty-calorie snacks."
        ),
        chunk_index=0,
        token_count=32,
    )


def _stub_model(settings: Settings | None = None) -> RunnableLambda:
    """A runnable that answers from the context packet it is given.

    Deliberately not a real model: it exists so the graph's routing, streaming
    and fail-closed validation can be demonstrated with no API key and no
    network. It quotes retrieved passages and cites their source ids, so
    citation validation exercises real behaviour rather than being stubbed out.
    """

    def generate(messages: list[dict[str, str]]) -> AIMessage:
        system = messages[0]["content"] if messages else ""
        cited = [line for line in system.splitlines() if line.startswith("[")]
        body = (
            "Here is what the reviewed source says.\n\n"
            "A balanced pregnancy diet should include iron-rich foods such as "
            "lentils, spinach and jaggery, plus protein, fruit and vegetables "
            "[src-demo-nutrition]."
        )
        del cited
        return AIMessage(content=body)

    return RunnableLambda(generate)


def _patch_stub() -> None:
    """Route the graph's generation node to the stub model."""

    langchain_provider.build_chat_model = lambda settings=None: _stub_model(settings)
    # build_generation_runnable resolves build_chat_model from its own module
    # globals, so patching there is enough; the pipeline module is patched only
    # so its get_settings lookups stay consistent with the graph.
    pipeline_module.get_settings = get_settings


def _print_result(result: object, query: str) -> None:
    assert hasattr(result, "answer")
    print("=" * 72)
    print(f"QUERY   : {query}")
    print("=" * 72)
    print()
    print("RESPONSE")
    print("-" * 72)
    print(result.answer)  # type: ignore[attr-defined]
    print()
    print("-" * 72)
    print("DIAGNOSTICS")
    print("-" * 72)
    print(f"  short_circuited : {result.short_circuited}")  # type: ignore[attr-defined]
    print(f"  risk_category   : {result.safety_result.risk_category}")  # type: ignore[attr-defined]
    print(f"  used_web_search : {result.used_web_search}")  # type: ignore[attr-defined]
    packet = result.context_packet  # type: ignore[attr-defined]
    if packet is not None:
        print(f"  sources_in_packet: {len(packet.retrieved_sources)}")
        print(f"  domains          : {[d for d in packet.evidence_summary.domains]}")
        print(f"  has_web_sources  : {bool(packet.web_sources)}")
        print(f"  context_tokens   : {packet.total_tokens}")
    citation = result.citation_result  # type: ignore[attr-defined]
    if citation is not None:
        print(f"  verified_cites   : {citation.verified_citation_ids}")
        print(f"  unverifiable     : {citation.unverifiable_citation_ids}")
    post = result.post_check_report  # type: ignore[attr-defined]
    if post is not None:
        print(f"  post_check_passed: {post.passed}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="The question to send through the graph")
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream the response tokens as delta events",
    )
    parser.add_argument(
        "--weak-evidence",
        action="store_true",
        help=(
            "Do not force a retrieval score, so the grounding gate decides on "
            "real keyword scores. Use this to exercise the "
            "insufficient-evidence route."
        ),
    )
    args = parser.parse_args(argv)

    _patch_stub()
    settings = get_settings()
    chunk = _demo_chunk()
    scores = None if args.weak_evidence else {chunk.chunk_id: 1.0}

    print()
    print(f"RAG_ORCHESTRATOR : {settings.rag_orchestrator}")
    print("MODEL            : stub (no API key, no network) - control-flow demo only")
    print()

    if args.stream:
        from app.rag.langgraph_flow import answer_query_graph_stream

        print("STREAMING")
        print("-" * 72)
        for event in answer_query_graph_stream(
            args.query,
            settings=settings,
            candidate_chunks=[chunk],
            candidate_scores=scores,
        ):
            if event.kind == "delta":
                print(event.text, end="", flush=True)
            else:
                print()
                print()
                print(f"[final] short_circuited={event.result.short_circuited if event.result else 'n/a'}")
        print()
        return 0

    compiled = build_graph(settings)
    result = answer_query_graph(
        args.query,
        settings=settings,
        candidate_chunks=[chunk],
        candidate_scores=scores,
        graph=compiled,
    )

    # Re-run with stream_mode="updates" to show which nodes actually executed
    # and in what order. This is the routing decision made visible.
    trace = compiled.stream(
        {"request": _request_for(args.query, chunk, scores)},
        stream_mode="updates",
    )
    nodes = [name for update in trace for name in update]

    print("GRAPH TRACE")
    print("-" * 72)
    print(f"  nodes executed : {' -> '.join(nodes)}")
    print()
    _print_result(result, args.query)
    return 0


if __name__ == "__main__":
    sys.exit(main())