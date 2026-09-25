"""Tests for app.rag.pipeline.answer_query_stream, the streaming counterpart
to answer_query (issue: POST /chat/stream). Verifies it shares
_prepare_generation/_finalize_generation with the blocking path exactly --
same safety short-circuit, same grounding gate, same post-check -- and only
differs in how the LLM is invoked.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.grounding import INSUFFICIENT_EVIDENCE_RESPONSE
from app.rag.pipeline import answer_query, answer_query_stream
from app.safety.post_check import SAFE_FALLBACK_RESPONSE
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk

CORPUS = [
    KnowledgeChunk(
        chunk_id="second-tri",
        document_id="doc-second-tri",
        source_id="src-second-tri",
        domain=Domain.NUTRITION,
        evidence_level=EvidenceLevel.SUPPORTED,
        content="Second trimester nutrition guidance recommends iron-rich foods for pregnancy",
        chunk_index=0,
    )
]


class FakeStreamingClient:
    """Only used to prove a client argument is threaded through -- the
    actual streaming call itself is monkeypatched at the module level in
    these tests (mirrors tests/test_chat_web_search.py's approach)."""


def collect(events):
    return list(events)


def test_stream_matches_blocking_answer_for_a_normal_grounded_query(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.rag.pipeline.stream_from_packet",
        lambda packet, client=None: iter(["Iron-rich foods ", "are recommended [src-second-tri]."]),
    )
    monkeypatch.setattr(
        "app.rag.pipeline.generate_from_packet",
        lambda packet, client=None: "Iron-rich foods are recommended [src-second-tri].",
    )

    query = "What nutrition is recommended in the second trimester?"
    blocking_result = answer_query(query, candidate_chunks=CORPUS)
    events = collect(answer_query_stream(query, candidate_chunks=CORPUS))

    deltas = [e for e in events if e.kind == "delta"]
    finals = [e for e in events if e.kind == "final"]
    assert len(finals) == 1
    streamed_text = "".join(e.text for e in deltas)
    assert streamed_text == "Iron-rich foods are recommended [src-second-tri]."
    assert finals[0].text == blocking_result.answer
    assert finals[0].result is not None
    assert finals[0].result.citation_result.is_clean == blocking_result.citation_result.is_clean


def test_stream_short_circuits_for_urgent_query_without_calling_the_llm(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("the LLM must never be called for a short-circuited query")

    monkeypatch.setattr("app.rag.pipeline.stream_from_packet", fail_if_called)

    events = collect(
        answer_query_stream("I'm bleeding and it's scaring me", candidate_chunks=CORPUS)
    )
    assert len(events) == 2
    assert events[0].kind == "delta"
    assert events[1].kind == "final"
    assert events[1].result.short_circuited is True
    assert events[1].result.safety_result.risk_category == "URGENT_ESCALATION"


def test_stream_insufficient_evidence_never_calls_the_llm(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("the LLM must never be called when evidence is insufficient")

    monkeypatch.setattr("app.rag.pipeline.stream_from_packet", fail_if_called)
    monkeypatch.setattr("app.rag.pipeline.get_settings", lambda: SimpleNamespace(tavily_api_key=""))

    events = collect(
        answer_query_stream("What is the capital of France?", candidate_chunks=CORPUS)
    )
    assert events[-1].kind == "final"
    assert events[-1].text == INSUFFICIENT_EVIDENCE_RESPONSE


def test_stream_mid_stream_failure_degrades_to_safe_fallback_not_a_crash(monkeypatch) -> None:
    def broken_stream(packet, client=None):
        yield "partial answer "
        raise ConnectionError("simulated network failure mid-stream")

    monkeypatch.setattr("app.rag.pipeline.stream_from_packet", broken_stream)

    events = collect(
        answer_query_stream(
            "What nutrition is recommended in the second trimester?", candidate_chunks=CORPUS
        )
    )
    deltas = [e for e in events if e.kind == "delta"]
    finals = [e for e in events if e.kind == "final"]
    assert deltas and deltas[0].text == "partial answer "
    assert len(finals) == 1
    # The partial, unvalidated text must never become the authoritative answer.
    assert finals[0].text == SAFE_FALLBACK_RESPONSE
    assert finals[0].text != "".join(d.text for d in deltas)
