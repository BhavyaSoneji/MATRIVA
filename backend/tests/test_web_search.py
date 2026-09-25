"""Tests for the Tavily web-search supplementary evidence source.

Mocks the Tavily HTTP call (via monkeypatching `requests.post`, same
mocking style pytest/monkeypatch already uses elsewhere in this suite) --
no live Tavily key is available in this environment, so these tests verify
wiring/behavior (used only when insufficient + configured, labeled
distinctly, degrades gracefully on failure, never reached for urgent/high
risk queries), not the quality of any real search result.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.rag.context_packet import WebSourceEntry, build_context_packet
from app.rag.grounding import INSUFFICIENT_EVIDENCE_RESPONSE
from app.rag.pipeline import answer_query
from app.rag.web_search import WebSearchResult, search_web
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk

CORPUS = [
    KnowledgeChunk(
        chunk_id="local-1",
        document_id="doc-local-1",
        source_id="src-local-1",
        domain=Domain.NUTRITION,
        evidence_level=EvidenceLevel.SUPPORTED,
        content="Iron-rich foods are recommended during pregnancy.",
        chunk_index=0,
    )
]

OUT_OF_CORPUS_QUERY = "What is the best telescope for viewing Saturn's rings?"


def make_response(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return make_response(self.content)


class FakeClient:
    def __init__(self, content: str):
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


class PoisonCompletions:
    def create(self, **kwargs):
        raise AssertionError("Groq should not have been called")


class PoisonClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=PoisonCompletions())


class FakeTavilyResponse:
    def __init__(self, payload=None, status=200):
        self._payload = payload or {}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


TAVILY_PAYLOAD = {
    "results": [
        {
            "title": "Saturn's rings - NASA",
            "url": "https://www.nasa.gov/saturn-rings",
            "content": "Saturn's rings are best viewed with a telescope of at least 70mm aperture.",
        },
        {
            "title": "Astronomy guide",
            "url": "https://www.astronomy.example/saturn",
            "content": "A 6-inch telescope reveals the Cassini Division.",
        },
    ]
}


# --- app.rag.web_search unit tests -----------------------------------------


def test_search_web_returns_empty_without_api_key() -> None:
    assert search_web("saturn's rings", api_key="") == []


def test_search_web_parses_tavily_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url, json, timeout):
        assert url == "https://api.tavily.com/search"
        assert json["query"] == "saturn's rings"
        assert json["api_key"] == "fake-key"
        return FakeTavilyResponse(TAVILY_PAYLOAD)

    monkeypatch.setattr("app.rag.web_search.requests.post", fake_post)
    results = search_web("saturn's rings", api_key="fake-key", max_results=2)
    assert results == [
        WebSearchResult(
            title="Saturn's rings - NASA",
            url="https://www.nasa.gov/saturn-rings",
            domain="nasa.gov",
            content="Saturn's rings are best viewed with a telescope of at least 70mm aperture.",
        ),
        WebSearchResult(
            title="Astronomy guide",
            url="https://www.astronomy.example/saturn",
            domain="astronomy.example",
            content="A 6-inch telescope reveals the Cassini Division.",
        ),
    ]


def test_search_web_degrades_to_empty_on_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args, **kwargs):
        import requests

        raise requests.ConnectionError("boom")

    monkeypatch.setattr("app.rag.web_search.requests.post", fake_post)
    assert search_web("anything", api_key="fake-key") == []


def test_search_web_degrades_to_empty_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.rag.web_search.requests.post", lambda *a, **k: FakeTavilyResponse(status=500)
    )
    assert search_web("anything", api_key="fake-key") == []


def test_search_web_degrades_to_empty_on_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.rag.web_search.requests.post", lambda *a, **k: FakeTavilyResponse({"unexpected": "shape"})
    )
    assert search_web("anything", api_key="fake-key") == []


# --- pipeline wiring tests ---------------------------------------------------


def test_web_search_not_used_when_key_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """No TAVILY_API_KEY configured -- must reproduce today's exact
    insufficient-evidence behavior, with the LLM never called."""
    monkeypatch.setattr("app.rag.pipeline.get_settings", lambda: SimpleNamespace(tavily_api_key=""))

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Tavily should not have been called without an API key")

    monkeypatch.setattr("app.rag.pipeline.search_web", fail_if_called)

    result = answer_query(OUT_OF_CORPUS_QUERY, candidate_chunks=CORPUS, client=PoisonClient())

    assert not result.short_circuited
    assert result.answer == INSUFFICIENT_EVIDENCE_RESPONSE
    assert result.context_packet.web_sources == []


def test_web_search_used_when_local_evidence_insufficient_and_key_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings", lambda: SimpleNamespace(tavily_api_key="fake-key")
    )
    calls: list[str] = []

    def fake_search_web(query, api_key, **kwargs):
        calls.append(query)
        assert api_key == "fake-key"
        return [
            WebSearchResult(
                title="Saturn's rings - NASA",
                url="https://www.nasa.gov/saturn-rings",
                domain="nasa.gov",
                content="Saturn's rings are best viewed with a telescope of at least 70mm aperture.",
            )
        ]

    monkeypatch.setattr("app.rag.pipeline.search_web", fake_search_web)
    client = FakeClient("A telescope with at least 70mm aperture works well [web1].")

    result = answer_query(OUT_OF_CORPUS_QUERY, candidate_chunks=CORPUS, client=client)

    assert calls == [OUT_OF_CORPUS_QUERY]
    assert not result.short_circuited
    assert result.used_web_search is True
    assert result.answer != INSUFFICIENT_EVIDENCE_RESPONSE
    assert client.completions.calls  # the LLM WAS called this time


def test_web_citations_are_labeled_distinctly_from_local_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings", lambda: SimpleNamespace(tavily_api_key="fake-key")
    )
    monkeypatch.setattr(
        "app.rag.pipeline.search_web",
        lambda *a, **k: [
            WebSearchResult(
                title="Saturn's rings - NASA",
                url="https://www.nasa.gov/saturn-rings",
                domain="nasa.gov",
                content="Saturn's rings are best viewed with a telescope of at least 70mm aperture.",
            )
        ],
    )
    client = FakeClient("A telescope with at least 70mm aperture works well [web1].")

    result = answer_query(OUT_OF_CORPUS_QUERY, candidate_chunks=CORPUS, client=client)

    packet = result.context_packet
    assert len(packet.web_sources) == 1
    web = packet.web_sources[0]
    assert web.source_type == "external_web"
    assert web.evidence_level == "uncertain"
    assert web.url == "https://www.nasa.gov/saturn-rings"
    assert web.domain == "nasa.gov"
    # The packet's rendered prompt keeps web sources in their own, clearly
    # labeled section, separate from RETRIEVED SOURCES.
    prompt_text = packet.to_prompt_text()
    assert "EXTERNAL WEB SOURCES" in prompt_text
    assert "UNVERIFIED" in prompt_text
    web_section_index = prompt_text.index("EXTERNAL WEB SOURCES")
    retrieved_section_index = prompt_text.index("RETRIEVED SOURCES")
    assert retrieved_section_index < web_section_index

    # The system prompt sent to Groq reinforces the same separation.
    system_message = client.completions.calls[0]["messages"][0]["content"]
    assert "EXTERNAL WEB SOURCES" in system_message
    # A [web1] citation is accepted (not stripped as unverifiable).
    assert result.citation_result.is_clean
    assert "web1" in result.citation_result.verified_citation_ids


def test_urgent_risk_short_circuits_before_web_search_is_ever_attempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings", lambda: SimpleNamespace(tavily_api_key="fake-key")
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("web search must never run before the safety short-circuit")

    monkeypatch.setattr("app.rag.pipeline.search_web", fail_if_called)

    result = answer_query(
        "I'm bleeding heavily and it's scaring me",
        candidate_chunks=CORPUS,
        client=PoisonClient(),
    )

    assert result.short_circuited
    assert result.safety_result.risk_category == "URGENT_ESCALATION"


def test_tavily_failure_degrades_to_insufficient_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Tavily API failure (search_web already swallows exceptions and
    returns []) must land on the same fixed insufficient-evidence response,
    never crash the request."""
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings", lambda: SimpleNamespace(tavily_api_key="fake-key")
    )
    monkeypatch.setattr("app.rag.pipeline.search_web", lambda *a, **k: [])

    result = answer_query(OUT_OF_CORPUS_QUERY, candidate_chunks=CORPUS, client=PoisonClient())

    assert not result.short_circuited
    assert result.answer == INSUFFICIENT_EVIDENCE_RESPONSE
    assert result.used_web_search is False


# --- context packet / citation validation unit tests -------------------------


def test_build_context_packet_defaults_to_no_web_sources() -> None:
    packet = build_context_packet("q", [], safety_result={})
    assert packet.web_sources == []
    assert "EXTERNAL WEB SOURCES" not in packet.to_prompt_text()


def test_build_context_packet_with_web_sources_renders_separate_section() -> None:
    web = WebSourceEntry(
        web_id="web1", title="t", url="https://example.com/a", domain="example.com", content="c"
    )
    packet = build_context_packet("q", [], safety_result={}, web_sources=[web])
    text = packet.to_prompt_text()
    assert "EXTERNAL WEB SOURCES" in text
    assert "https://example.com/a" in text
    assert "example.com" in text
