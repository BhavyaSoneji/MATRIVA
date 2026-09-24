import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from groq import APIConnectionError, APIStatusError, APITimeoutError

from app.llm import groq_client
from app.llm.groq_client import GenerationError, generate_from_packet
from app.llm.prompts import SOURCE_GROUNDED_SYSTEM_PROMPT
from app.rag.context_packet import build_context_packet

_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def make_packet():
    return build_context_packet("What should I eat?", [], safety_result={"risk_category": "SAFE_GENERAL"})


def make_response(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeCompletions:
    def __init__(self, responses=None, errors=None):
        self.responses = list(responses or [])
        self.errors = list(errors or [])
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, completions: FakeCompletions):
        self.chat = SimpleNamespace(completions=completions)


def test_missing_api_key_raises_before_any_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Groq API key not configured"):
        generate_from_packet(make_packet())


def test_successful_first_attempt_returns_content() -> None:
    completions = FakeCompletions(responses=[make_response("Eat iron-rich foods.")])
    client = FakeClient(completions)

    result = generate_from_packet(make_packet(), client=client)

    assert result == "Eat iron-rich foods."
    assert len(completions.calls) == 1


def test_system_prompt_is_sent_and_matches_section_58() -> None:
    completions = FakeCompletions(responses=[make_response("answer")])
    client = FakeClient(completions)

    generate_from_packet(make_packet(), client=client)

    sent_messages = completions.calls[0]["messages"]
    assert sent_messages[0] == {"role": "system", "content": SOURCE_GROUNDED_SYSTEM_PROMPT}
    for required_phrase in (
        "Do not invent medical facts",
        "Do not fabricate",
        "Do not imply that traditional knowledge has modern clinical validation",
        "If the evidence is insufficient",
        "Do not diagnose",
    ):
        assert required_phrase in SOURCE_GROUNDED_SYSTEM_PROMPT


def test_retries_on_connection_error_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(groq_client.time, "sleep", lambda _seconds: None)
    completions = FakeCompletions(
        responses=[make_response("answer after retry")],
        errors=[APIConnectionError(request=_REQUEST)],
    )
    client = FakeClient(completions)

    result = generate_from_packet(make_packet(), client=client, max_retries=3)

    assert result == "answer after retry"
    assert len(completions.calls) == 2


def test_retries_on_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(groq_client.time, "sleep", lambda _seconds: None)
    completions = FakeCompletions(
        responses=[make_response("ok")],
        errors=[APITimeoutError(request=_REQUEST)],
    )
    client = FakeClient(completions)

    result = generate_from_packet(make_packet(), client=client)
    assert result == "ok"


def test_exhausting_retries_raises_generation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(groq_client.time, "sleep", lambda _seconds: None)
    completions = FakeCompletions(
        errors=[
            APIConnectionError(request=_REQUEST),
            APIConnectionError(request=_REQUEST),
            APIConnectionError(request=_REQUEST),
        ]
    )
    client = FakeClient(completions)

    with pytest.raises(GenerationError, match="failed after 3 attempts"):
        generate_from_packet(make_packet(), client=client, max_retries=3)
    assert len(completions.calls) == 3


def test_non_retryable_api_status_error_fails_immediately() -> None:
    response = httpx.Response(400, request=_REQUEST)
    completions = FakeCompletions(
        errors=[APIStatusError("bad request", response=response, body=None)]
    )
    client = FakeClient(completions)

    with pytest.raises(GenerationError, match="non-retryable"):
        generate_from_packet(make_packet(), client=client, max_retries=3)
    assert len(completions.calls) == 1  # no retry attempted
