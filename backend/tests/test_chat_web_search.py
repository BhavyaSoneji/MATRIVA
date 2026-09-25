"""End-to-end (HTTP layer) tests for web-search augmentation of /chat.

Exercises app.services.chat.process_chat -> app.rag.pipeline.answer_question
-> answer_query, with Groq and Tavily both mocked out (no live keys are
configured in this environment) -- verifies that a web-grounded answer
actually reaches the /chat response as a distinctly-labeled citation, and
that the local-only insufficient-evidence path is completely unaffected
when Tavily isn't configured.
"""

from types import SimpleNamespace

from fastapi.testclient import TestClient

QUERY = "What is the best telescope for viewing Saturn's rings?"


def _fake_settings(llm_api_key: str = "", tavily_api_key: str = ""):
    return SimpleNamespace(llm_api_key=llm_api_key, tavily_api_key=tavily_api_key)


def test_chat_uses_web_search_when_local_evidence_insufficient_and_configured(
    client: TestClient, monkeypatch
) -> None:
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
    monkeypatch.setattr(
        "app.rag.pipeline.generate_from_packet",
        lambda packet, client=None: "A 70mm-aperture telescope works well for viewing Saturn's rings [web1].",
    )

    response = client.post("/chat", json={"message": QUERY})

    assert response.status_code == 200
    body = response.json()
    assert "telescope" in body["answer"].lower()
    web_citations = [c for c in body["citations"] if c["source_type"] == "external_web"]
    assert len(web_citations) == 1
    assert web_citations[0]["url"] == "https://www.nasa.gov/saturn-rings"
    assert web_citations[0]["domain"] == "nasa.gov"
    assert web_citations[0]["evidence_level"] == "uncertain"
    assert body["evidence"]["web_search_used"] is True


def test_chat_insufficient_evidence_unchanged_when_tavily_not_configured(
    client: TestClient, monkeypatch
) -> None:
    """No TAVILY_API_KEY -- must behave exactly like before this feature:
    the fixed insufficient-evidence response, no web citations."""
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings",
        lambda: _fake_settings(llm_api_key="fake-groq-key", tavily_api_key=""),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Tavily must never be called when TAVILY_API_KEY is not configured")

    monkeypatch.setattr("app.rag.pipeline.search_web", fail_if_called)

    response = client.post("/chat", json={"message": QUERY})

    assert response.status_code == 200
    body = response.json()
    assert body["safety_status"] == "insufficient_information"
    assert body["citations"] == []
    assert body["evidence"]["web_search_used"] is False


def test_chat_urgent_symptoms_never_reach_web_search(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.rag.pipeline.get_settings",
        lambda: _fake_settings(llm_api_key="fake-groq-key", tavily_api_key="fake-tavily-key"),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("web search must never run for an urgent-risk query")

    monkeypatch.setattr("app.rag.pipeline.search_web", fail_if_called)

    response = client.post("/chat", json={"message": "I have heavy bleeding and severe headache"})

    assert response.status_code == 200
    body = response.json()
    assert body["safety_status"] == "urgent_escalation"
