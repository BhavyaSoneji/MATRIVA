from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.core.db import SessionLocal
from app.llm import langchain_provider
from app.models import (
    EvidenceLevel as EvidenceLevelValue,
    IndexStatus,
    KnowledgeChunk as KnowledgeChunkRow,
    KnowledgeDocument,
    KnowledgeSource,
    ReviewStatus,
)
from app.rag import embeddings
from app.rag.pipeline import answer_query, answer_question, answer_query_stream
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk


def _chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        source_id="src-nutrition-1",
        domain=Domain.NUTRITION,
        topic="pregnancy nutrition",
        pregnancy_stage="first_trimester",
        evidence_level=EvidenceLevel.SUPPORTED,
        language="en",
        content="During pregnancy, eat a balanced diet with iron, protein, fruit and vegetables.",
        chunk_index=0,
        token_count=14,
    )


def _langchain_settings(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "rag_orchestrator": "langchain",
        "rag_engine": "external",
        "llm_api_key": "fake-langchain-key",
        "llm_model": "openai/gpt-oss-120b",
        "tavily_api_key": "",
        "embedding_api_key": "",
        "embedding_model": embeddings.EMBEDDING_MODEL,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_langchain_blocking_chain_generates_cited_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _langchain_settings()
    seen_messages: list[Any] = []

    def fake_model(_settings=None):
        def generate(messages: list[dict[str, str]]) -> AIMessage:
            seen_messages.extend(messages)
            return AIMessage(content="Eat iron-rich foods and fruit every day [src-nutrition-1].")

        return RunnableLambda(generate)

    monkeypatch.setattr("app.rag.pipeline.get_settings", lambda: settings)
    monkeypatch.setattr(langchain_provider, "build_chat_model", fake_model)

    result = answer_query(
        "What should I eat during pregnancy?",
        candidate_chunks=[_chunk()],
        candidate_scores={"chunk-1": 1.0},
    )

    assert not result.short_circuited
    assert "iron-rich" in result.answer
    assert result.context_packet is not None
    assert result.post_check_report is not None
    assert any("RETRIEVED SOURCES" in message["content"] for message in seen_messages)


def test_langchain_urgent_short_circuit_never_builds_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(_settings=None):
        raise AssertionError("the LangChain model must never be constructed for an urgent query")

    monkeypatch.setattr("app.rag.pipeline.get_settings", lambda: _langchain_settings())
    monkeypatch.setattr(langchain_provider, "build_chat_model", fail_if_called)

    result = answer_query(
        "I have heavy bleeding and severe abdominal pain",
        candidate_chunks=[_chunk()],
    )

    assert result.short_circuited
    assert "care provider" in result.answer.lower()
    assert "emergency" in result.answer.lower()


def test_langchain_insufficient_evidence_never_builds_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(_settings=None):
        raise AssertionError("the LangChain model must not run without sufficient evidence")

    monkeypatch.setattr("app.rag.pipeline.get_settings", lambda: _langchain_settings())
    monkeypatch.setattr(langchain_provider, "build_chat_model", fail_if_called)

    result = answer_query(
        "What is the capital of France?",
        candidate_chunks=[_chunk()],
    )

    assert not result.short_circuited
    assert "don't have enough" in result.answer.lower()


def test_langchain_streaming_chain_streams_and_finalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeChunk:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeStreamingModel:
        def stream(self, messages: list[dict[str, str]]):
            assert messages[0]["role"] == "system"
            yield FakeChunk("Eat iron-rich foods ")
            yield FakeChunk("and fruit every day [src-nutrition-1].")

    monkeypatch.setattr(
        "app.rag.pipeline.get_settings", lambda: _langchain_settings()
    )
    monkeypatch.setattr(
        langchain_provider, "build_chat_model", lambda _settings=None: FakeStreamingModel()
    )

    events = list(
        answer_query_stream(
            "What should I eat during pregnancy?",
            candidate_chunks=[_chunk()],
            candidate_scores={"chunk-1": 1.0},
        )
    )
    deltas = [event.text for event in events if event.kind == "delta"]
    finals = [event for event in events if event.kind == "final"]

    assert "".join(deltas) == "Eat iron-rich foods and fruit every day [src-nutrition-1]."
    assert len(finals) == 1
    assert finals[0].result is not None
    assert "iron-rich" in finals[0].text


def test_langchain_embedding_provider_uses_query_and_document_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    class FakeEmbeddings:
        def embed_query(self, text: str) -> list[float]:
            calls["query"] = text
            return [0.1, 0.2]

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            calls["documents"] = texts
            return [[float(len(text))] for text in texts]

    monkeypatch.setattr(
        embeddings, "get_settings", lambda: _langchain_settings(embedding_api_key="gemini-key")
    )
    monkeypatch.setattr(embeddings, "_langchain_embeddings", lambda _key, _model: FakeEmbeddings())

    assert embeddings.embed_text("query", api_key="gemini-key") == [0.1, 0.2]
    assert embeddings.embed_chunk_contents(["a", "bb"], api_key="gemini-key") == [[1.0], [2.0]]
    assert calls == {"query": "query", "documents": ["a", "bb"]}


def test_langchain_db_to_response_adapter_uses_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _langchain_settings()
    monkeypatch.setattr("app.rag.pipeline.get_settings", lambda: settings)
    monkeypatch.setattr(
        langchain_provider,
        "build_chat_model",
        lambda _settings=None: RunnableLambda(
            lambda _messages: AIMessage(
                content="Choose iron-rich foods, fruit and protein [src-db-1]."
            )
        ),
    )

    with SessionLocal() as db:
        source = KnowledgeSource(
            id="src-db-1",
            name="Demo nutrition source",
            title="Pregnancy nutrition basics",
            source_type="internal",
            topic="pregnancy nutrition",
            review_status=ReviewStatus.APPROVED.value,
            evidence_level=EvidenceLevelValue.SUPPORTED.value,
        )
        document = KnowledgeDocument(
            id="doc-db-1",
            source_id=source.id,
            title="Pregnancy nutrition basics",
            domain="nutrition",
            language="en",
            review_status=ReviewStatus.APPROVED.value,
            index_status=IndexStatus.INDEXED.value,
            content_hash="langchain-db-adapter-hash",
            active=True,
        )
        chunk = KnowledgeChunkRow(
            id="chunk-db-1",
            document_id=document.id,
            source_id=source.id,
            chunk_index=0,
            content="During pregnancy choose iron-rich foods, fruit, vegetables and protein.",
        )
        db.add_all([source, document, chunk])
        db.commit()

        generation, retrieved = answer_question(
            db,
            "What should I eat during pregnancy?",
        )

    assert generation.used_external_provider is True
    assert "iron-rich" in generation.text
    assert generation.citation_ids == ["src-db-1"]
    assert [item.chunk.id for item in retrieved] == ["chunk-db-1"]