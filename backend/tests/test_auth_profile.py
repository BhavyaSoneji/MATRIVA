from fastapi.testclient import TestClient


def test_register_login_and_password_is_hashed(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "person@example.com", "password": "StrongPass123"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    assert token

    login = client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]

    from app.core.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        user = db.query(User).filter_by(email="person@example.com").one()
        assert user.password_hash != "StrongPass123"
        assert user.password_hash.startswith("pbkdf2_sha256$")


def test_auth_rate_limit_is_enforced(client: TestClient, monkeypatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 2)
    payload = {"email": "rate@example.com", "password": "StrongPass123"}
    assert client.post("/auth/login", json=payload).status_code == 401
    assert client.post("/auth/login", json=payload).status_code == 401
    limited = client.post("/auth/login", json=payload)
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]


def test_profile_requires_consent_and_pregnancy_is_validated(client: TestClient, auth_headers: dict[str, str]) -> None:
    denied = client.put("/profile", headers=auth_headers, json={"consent": False, "region": "Gujarat"})
    assert denied.status_code == 403

    accepted = client.put(
        "/profile",
        headers=auth_headers,
        json={"consent": True, "region": "Gujarat", "diet_type": "vegetarian"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["dietary"]["region"] == "Gujarat"

    pregnancy = client.put("/pregnancy", headers=auth_headers, json={"current_week": 14})
    assert pregnancy.status_code == 200
    assert pregnancy.json()["stage"] == "second_trimester"

    invalid = client.put("/pregnancy", headers=auth_headers, json={"current_week": 50})
    assert invalid.status_code == 422


def test_chat_does_not_mutate_profile_from_session_context(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.put("/profile", headers=auth_headers, json={"consent": True})
    response = client.post(
        "/chat",
        headers=auth_headers,
        json={"message": "I have been stressed lately", "session_context": {"note": "session-only"}},
    )
    assert response.status_code == 200
    profile = client.get("/profile", headers=auth_headers)
    assert profile.status_code == 200
    assert profile.json()["lifestyle"]["stress_level"] is None


def test_consent_withdrawal_removes_profile_data(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.put("/profile", headers=auth_headers, json={"consent": True, "region": "Gujarat"})
    client.put("/pregnancy", headers=auth_headers, json={"current_week": 20})
    response = client.post("/privacy/consent", headers=auth_headers, json={"granted": False, "version": "2026-01"})
    assert response.status_code == 200
    profile = client.get("/profile", headers=auth_headers)
    assert profile.status_code == 200
    assert profile.json()["consent"] is False
    assert client.get("/pregnancy", headers=auth_headers).status_code == 404
