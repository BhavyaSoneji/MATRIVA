from fastapi.testclient import TestClient


def test_health_and_demo_anc_endpoint(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    response = client.get("/pregnancy/next-visit?current_week=18")
    assert response.status_code == 200
    assert response.json()["next_visit_week"] == 20


def test_chat_fails_closed_for_urgent_symptoms(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "I have heavy bleeding and severe headache"})
    assert response.status_code == 200
    body = response.json()
    assert body["safety_status"] == "urgent_escalation"
    assert "professional" in body["answer"].lower()
    assert "emergency" in body["answer"].lower()
    assert body["sources"] == []


def test_invalid_bearer_token_does_not_become_demo_access(client: TestClient) -> None:
    response = client.post(
        "/chat",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"message": "hello"},
    )
    assert response.status_code == 401


def test_safety_subsystem_failure_fails_closed(client: TestClient, monkeypatch) -> None:
    def broken_classifier(*_args, **_kwargs):
        raise RuntimeError("classifier unavailable")

    monkeypatch.setattr("app.services.chat.classify_query", broken_classifier)
    response = client.post("/chat", json={"message": "What should I eat?"})
    assert response.status_code == 503
    body = response.json()
    assert "cannot safely" in body["answer"].lower()
    assert body["sources"] == []
    assert body["evidence"]["citation_validation"] == "blocked"
