from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite:///./test_matriva.db"
os.environ["JWT_SECRET"] = "test-secret-012345678901234567890123456789"
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEMO_MODE"] = "true"
os.environ["AUTO_CREATE_TABLES"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.core.db import Base, engine
from app.core.rate_limit import rate_limiter
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_limiter.clear()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "StrongPass123", "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    response = client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "StrongPass123", "full_name": "Admin"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    from app.core.db import SessionLocal
    from app.models import User, UserRole

    with SessionLocal() as db:
        user = db.query(User).filter_by(email="admin@example.com").one()
        user.role = UserRole.ADMIN.value
        db.commit()
    return {"Authorization": f"Bearer {token}"}
