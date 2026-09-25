"""Tests for POST /chat/stream (app.api.chat.chat_stream / app.services.chat.stream_chat).

Wire format under test (see stream_chat's docstring for the authoritative
contract): each SSE frame is "event: <type>\\ndata: <json>\\n\\n" with types
"delta", "final", "done", "error". No live Groq/Tavily keys exist in this
environment, so the LLM/search calls are mocked at the same seams
tests/test_chat_web_search.py already uses (app.rag.pipeline.get_settings,
search_web, generate_from_packet) plus the new streaming entry point
app.rag.pipeline.stream_from_packet.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

QUERY = "What is the best telescope for viewing Saturn's rings?"


def _fake_settings(llm_api_key: str = "", tavily_api_key: str = ""):
    return SimpleNamespace(llm_api_key=llm_api_key, tavily_api_key=tavily_api_key)


def parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.splitlines():
            if line.startswith("event:"):
                event_type = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:") :].strip())
        events.append({"event": event_type, "data": data})
    return events


def _configure_web_augmented(monkeypatch, stream_chunks: list[str], blocking_text: str) -> None:
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings",
        lambda: _fake_settings(llm_api_key="fake-groq-key", tavily_api_key="fake-tavily-key"),
    )
    monkeypatch.setattr(
        "app.rag.pipeline.search_web",
        lambda query, api_key, **kwargs: [
            SimpleNamespace(
                title="Saturn's rings - NASA",
                url="https://www.nasa.gov/saturn-rings",
                domain="nasa.gov",
                content="Saturn's rings are best viewed with a telescope of at least 70mm aperture.",
            )
        ],
    )
    monkeypatch.setattr("app.rag.pipeline.generate_from_packet", lambda packet, client=None: blocking_text)
    monkeypatch.setattr("app.rag.pipeline.stream_from_packet", lambda packet, client=None: iter(stream_chunks))


def test_stream_completes_with_same_final_answer_as_non_streaming(client: TestClient, monkeypatch) -> None:
    answer_text = "A 70mm-aperture telescope works well for viewing Saturn's rings [web1]."
    _configure_web_augmented(
        monkeypatch,
        stream_chunks=["A 70mm-aperture telescope ", "works well for viewing Saturn's rings [web1]."],
        blocking_text=answer_text,
    )

    blocking_response = client.post("/chat", json={"message": QUERY})
    assert blocking_response.status_code == 200
    blocking_body = blocking_response.json()

    streamed_response = client.post("/chat/stream", json={"message": QUERY})
    assert streamed_response.status_code == 200
    assert streamed_response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(streamed_response.text)

    delta_events = [e for e in events if e["event"] == "delta"]
    final_events = [e for e in events if e["event"] == "final"]
    done_events = [e for e in events if e["event"] == "done"]
    assert len(final_events) == 1
    assert len(done_events) == 1

    streamed_text = "".join(e["data"]["text"] for e in delta_events)
    final_data = final_events[0]["data"]
    assert streamed_text == answer_text
    assert final_data["answer"] == answer_text
    assert final_data["corrected"] is False
    assert final_data["answer"] == blocking_body["answer"]

    web_citations = [c for c in final_data["citations"] if c["source_type"] == "external_web"]
    assert len(web_citations) == 1
    assert web_citations[0]["url"] == "https://www.nasa.gov/saturn-rings"

    done_data = done_events[0]["data"]
    assert done_data["conversation_id"]
    assert done_data["message_id"]


def test_stream_post_check_failure_sends_corrective_final_event(client: TestClient, monkeypatch) -> None:
    """The streamed tokens assemble into a dangerous-recommendation answer
    that the safety post-check must reject -- the "final" event must carry
    the safe fallback with corrected=True, not the streamed text."""
    dangerous_text = "You should stop taking your medication now that you feel better."
    _configure_web_augmented(
        monkeypatch,
        stream_chunks=["You should stop taking ", "your medication now that you feel better."],
        blocking_text=dangerous_text,
    )

    response = client.post("/chat/stream", json={"message": QUERY})
    assert response.status_code == 200
    events = parse_sse(response.text)

    delta_events = [e for e in events if e["event"] == "delta"]
    final_events = [e for e in events if e["event"] == "final"]
    streamed_text = "".join(e["data"]["text"] for e in delta_events)
    assert streamed_text == dangerous_text

    final_data = final_events[0]["data"]
    assert final_data["corrected"] is True
    assert final_data["answer"] != dangerous_text
    assert "stop taking your medication" not in final_data["answer"].lower()


def test_stream_urgent_risk_short_circuits_without_calling_the_llm(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings",
        lambda: _fake_settings(llm_api_key="fake-groq-key", tavily_api_key="fake-tavily-key"),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("the LLM/search must never be called for an urgent-risk query")

    monkeypatch.setattr("app.rag.pipeline.search_web", fail_if_called)
    monkeypatch.setattr("app.rag.pipeline.generate_from_packet", fail_if_called)
    monkeypatch.setattr("app.rag.pipeline.stream_from_packet", fail_if_called)

    response = client.post("/chat/stream", json={"message": "I have heavy bleeding and severe headache"})
    assert response.status_code == 200
    events = parse_sse(response.text)

    final_events = [e for e in events if e["event"] == "final"]
    assert len(final_events) == 1
    assert final_events[0]["data"]["safety_status"] == "urgent_escalation"
    assert "professional" in final_events[0]["data"]["answer"].lower()


def test_stream_with_zero_local_evidence_and_no_tavily_still_sends_a_delta(
    client: TestClient, monkeypatch
) -> None:
    """Regression test: answer_question_stream's zero-local-evidence-and-
    no-Tavily branch has nothing to stream token-by-token and used to emit
    ONLY a "final" event -- the frontend would show nothing at all until
    that arrived, contradicting the documented "every query gets at least
    one delta before final" contract that the safety-short-circuit and
    no-key branches already followed. stream_chat now synthesizes one delta
    covering the whole insufficient-evidence answer in this case too."""
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings",
        lambda: _fake_settings(llm_api_key="fake-groq-key", tavily_api_key=""),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("no local evidence and no Tavily key -- the LLM must never be called")

    monkeypatch.setattr("app.rag.pipeline.generate_from_packet", fail_if_called)
    monkeypatch.setattr("app.rag.pipeline.stream_from_packet", fail_if_called)

    response = client.post("/chat/stream", json={"message": QUERY})
    assert response.status_code == 200
    events = parse_sse(response.text)

    delta_events = [e for e in events if e["event"] == "delta"]
    final_events = [e for e in events if e["event"] == "final"]
    assert len(final_events) == 1
    assert len(delta_events) >= 1, "frontend must receive at least one delta before final, even here"
    assert "".join(e["data"]["text"] for e in delta_events) == final_events[0]["data"]["answer"]
    assert final_events[0]["data"]["corrected"] is False


def test_stream_requires_auth_when_not_in_demo_mode(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.api.chat.get_settings", lambda: SimpleNamespace(demo_mode=False))
    response = client.post("/chat/stream", json={"message": "hello"})
    assert response.status_code == 401
