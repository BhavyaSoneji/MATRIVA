"""Tests for the LangGraph orchestration path (issue #116).

The point of these tests is that LangGraph is *routing*, not deciding policy.
So each one pins a property the other orchestrators must also hold:

- the graph produces the same PipelineResult shape as LCEL and native
- a safety short-circuit never constructs a provider client
- a grounding-gate failure routes to `complete`, never to `generate`
- generation and finalization both actually run on the normal path
- streaming reuses the same prepare decision and still fails closed
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.core.config import Settings
from app.llm import langchain_provider
from app.rag.langgraph_flow import answer_query_graph, answer_query_graph_stream, build_graph
from app.rag.pipeline import answer_query
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk, SourceType

ANSWER = "Eat iron-rich foods such as lentils and spinach every day [src-nutrition-1]."


def _chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        source_id="src-nutrition-1",
        domain=Domain.NUTRITION,
        topic="pregnancy nutrition",
        evidence_level=EvidenceLevel.SUPPORTED,
        source_type=SourceType.NUTRITION_REFERENCE,
        language="en",
        content=(
            "During pregnancy, eat a balanced diet with iron, protein, fruit and "
            "vegetables. Iron-rich foods such as lentils and spinach help."
        ),
        chunk_index=0,
        token_count=22,
    )


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "rag_orchestrator": "langgraph",
        "rag_engine": "external",
        "llm_api_key": "fake-langchain-key",
        "llm_model": "openai/gpt-oss-120b",
        "tavily_api_key": "",
        "embedding_api_key": "",
        "embedding_model": "models/gemini-embedding-001",
    }
    base.update(overrides)
    return Settings(**base)


def _stub_model(seen: list[Any] | None = None) -> Any:
    def generate(messages: list[dict[str, str]]) -> AIMessage:
        if seen is not None:
            seen.extend(messages)
        return AIMessage(content=ANSWER)

    return lambda _settings=None: RunnableLambda(generate)


# --- graph construction and routing ----------------------------------------


def test_graph_executes_prepare_generate_finalize(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    graph = build_graph(settings)
    monkeypatch.setattr(langchain_provider, "build_chat_model", _stub_model())

    from app.rag.langgraph_flow import GraphRequest

    request = GraphRequest(
        query="What should I eat during pregnancy?",
        candidate_chunks=[_chunk()],
        candidate_scores={"chunk-1": 1.0},
    )
    nodes = [name for update in graph.stream({"request": request}, stream_mode="updates") for name in update]

    assert nodes == ["prepare", "generate", "finalize"]


def test_urgent_query_routes_to_complete_and_never_builds_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(_settings=None):
        raise AssertionError("no provider client may be constructed for an urgent query")

    graph = build_graph(_settings())
    monkeypatch.setattr(langchain_provider, "build_chat_model", fail_if_called)

    result = answer_query_graph(
        "I have heavy bleeding and severe abdominal pain",
        settings=_settings(),
        candidate_chunks=[_chunk()],
        graph=graph,
    )

    assert result.short_circuited is True
    assert "care provider" in result.answer.lower()
    assert result.context_packet is None
    assert result.citation_result is None


def test_insufficient_evidence_routes_to_complete_without_generating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(_settings=None):
        raise AssertionError("the grounding gate must stop the graph before generation")

    graph = build_graph(_settings())
    monkeypatch.setattr(langchain_provider, "build_chat_model", fail_if_called)

    result = answer_query_graph(
        "What is the capital of France?",
        settings=_settings(),
        candidate_chunks=[_chunk()],
        graph=graph,
    )

    assert "don't have enough evidence" in result.answer.lower()
    assert result.context_packet is not None
    assert result.citation_result is None


def test_graph_answer_is_cited_and_post_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []
    monkeypatch.setattr(langchain_provider, "build_chat_model", _stub_model(seen))

    result = answer_query_graph(
        "What should I eat during pregnancy?",
        settings=_settings(),
        candidate_chunks=[_chunk()],
        candidate_scores={"chunk-1": 1.0},
    )

    assert result.short_circuited is False
    assert result.answer == ANSWER
    assert result.context_packet is not None
    assert result.citation_result is not None
    assert result.citation_result.verified_citation_ids == ["src-nutrition-1"]
    assert result.citation_result.unverifiable_citation_ids == []
    assert result.post_check_report is not None
    assert result.post_check_report.passed is True
    assert any("RETRIEVED SOURCES" in message["content"] for message in seen)


def test_invalid_citations_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fabricated citation must not reach the user."""

    monkeypatch.setattr(
        langchain_provider,
        "build_chat_model",
        lambda _settings=None: RunnableLambda(
            lambda _m: AIMessage(content="Eat iron-rich foods daily [src-does-not-exist].")
        ),
    )

    result = answer_query_graph(
        "What should I eat during pregnancy?",
        settings=_settings(),
        candidate_chunks=[_chunk()],
        candidate_scores={"chunk-1": 1.0},
    )

    assert "src-does-not-exist" not in result.answer


def test_graph_is_reusable_across_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    """The compiled graph holds no per-call state, so it can be reused."""

    monkeypatch.setattr(langchain_provider, "build_chat_model", _stub_model())
    graph = build_graph(_settings())

    first = answer_query_graph(
        "What should I eat during pregnancy?",
        settings=_settings(),
        candidate_chunks=[_chunk()],
        candidate_scores={"chunk-1": 1.0},
        graph=graph,
    )
    second = answer_query_graph(
        "I have heavy bleeding",
        settings=_settings(),
        candidate_chunks=[_chunk()],
        graph=graph,
    )
    third = answer_query_graph(
        "Which foods have iron?",
        settings=_settings(),
        candidate_chunks=[_chunk()],
        candidate_scores={"chunk-1": 1.0},
        graph=graph,
    )

    assert first.answer == ANSWER
    assert second.short_circuited is True
    assert third.answer == ANSWER


# --- streaming --------------------------------------------------------------


def test_graph_stream_streams_then_finalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChunk:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeStreamingModel:
        def stream(self, messages: list[dict[str, str]]):
            assert messages[0]["role"] == "system"
            yield FakeChunk("Eat iron-rich foods ")
            yield FakeChunk("such as lentils and spinach every day [src-nutrition-1].")

    monkeypatch.setattr(
        langchain_provider, "build_chat_model", lambda _settings=None: FakeStreamingModel()
    )

    events = list(
        answer_query_graph_stream(
            "What should I eat during pregnancy?",
            settings=_settings(),
            candidate_chunks=[_chunk()],
            candidate_scores={"chunk-1": 1.0},
        )
    )

    deltas = [e.text for e in events if e.kind == "delta"]
    finals = [e for e in events if e.kind == "final"]

    assert "".join(deltas) == ANSWER
    assert len(finals) == 1
    assert finals[0].result is not None
    assert finals[0].result.post_check_report is not None


def test_graph_stream_short_circuits_without_touching_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(_settings=None):
        raise AssertionError("a short-circuited stream must not build a provider")

    monkeypatch.setattr(langchain_provider, "build_chat_model", fail_if_called)

    events = list(
        answer_query_graph_stream(
            "I have heavy bleeding",
            settings=_settings(),
            candidate_chunks=[_chunk()],
        )
    )

    assert [e.kind for e in events] == ["delta", "final"]
    assert events[-1].result is not None
    assert events[-1].result.short_circuited is True


def test_graph_stream_provider_failure_yields_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenModel:
        def stream(self, _messages: list[dict[str, str]]):
            yield type("Chunk", (), {"content": "partial, unvalidated "})()
            raise RuntimeError("network dropped mid-stream")

    monkeypatch.setattr(langchain_provider, "build_chat_model", lambda _settings=None: BrokenModel())

    events = list(
        answer_query_graph_stream(
            "What should I eat during pregnancy?",
            settings=_settings(),
            candidate_chunks=[_chunk()],
            candidate_scores={"chunk-1": 1.0},
        )
    )

    finals = [e for e in events if e.kind == "final"]
    assert len(finals) == 1
    assert finals[0].result is not None
    # Partial text must never be presented as the authoritative answer.
    assert "partial, unvalidated" not in finals[0].text


# --- settings wiring --------------------------------------------------------


def test_langgraph_orchestrator_routes_answer_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """`RAG_ORCHESTRATOR=langgraph` must actually reach the graph."""

    seen: dict[str, Any] = {}
    monkeypatch.setattr(langchain_provider, "build_chat_model", _stub_model())
    sentinel = answer_query_graph(
        "What should I eat during pregnancy?",
        settings=_settings(),
        candidate_chunks=[_chunk()],
        candidate_scores={"chunk-1": 1.0},
    )

    def spy(query: str, **kwargs: Any):
        seen["query"] = query
        seen["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr("app.rag.pipeline.get_settings", lambda: SimpleNamespace(rag_orchestrator="langgraph"))
    monkeypatch.setattr(
        "app.rag.langgraph_flow.answer_query_graph",
        spy,
    )

    result = answer_query("What should I eat during pregnancy?", candidate_chunks=[_chunk()])

    assert seen["query"] == "What should I eat during pregnancy?"
    assert result is sentinel


def test_unknown_orchestrator_falls_back_to_native(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings",
        lambda: SimpleNamespace(rag_orchestrator="something-else"),
    )
    monkeypatch.setattr(
        "app.rag.pipeline.generate_from_packet",
        lambda packet, client=None: ANSWER,
    )

    result = answer_query(
        "What should I eat during pregnancy?",
        candidate_chunks=[_chunk()],
        candidate_scores={"chunk-1": 1.0},
    )

    assert result.answer == ANSWER