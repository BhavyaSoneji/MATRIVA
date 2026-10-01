import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.ingest_real_knowledge as ingest_module
from app.core.db import SessionLocal
from app.models import FoodItem, Guideline, KnowledgeDocument


def _upload(client: TestClient, headers: dict[str, str], title: str) -> str:
    metadata = {"title": title, "domain": "nutrition", "source_name": title, "source_type": "government",
                "authority": "Test authority", "evidence_level": "supported"}
    res = client.post(
        "/admin/documents", headers=headers, data={"metadata": json.dumps(metadata)},
        files={"file": ("s.txt", f"{title} body text about balanced meals.".encode(), "text/plain")},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_preview_returns_text_and_source_details(client: TestClient, admin_headers: dict[str, str]) -> None:
    doc_id = _upload(client, admin_headers, "Preview me")
    client.post(f"/admin/documents/{doc_id}/reindex", headers=admin_headers)
    body = client.get(f"/admin/documents/{doc_id}/preview", headers=admin_headers).json()
    assert "balanced meals" in body["excerpt"]
    assert body["chunk_count"] >= 1
    assert body["authority"] == "Test authority"
    assert client.get("/admin/documents/nope/preview", headers=admin_headers).status_code == 404


def test_bulk_approve_approves_indexed_and_reports_skips(client: TestClient, admin_headers: dict[str, str]) -> None:
    good = _upload(client, admin_headers, "Bulk good")
    client.post(f"/admin/documents/{good}/reindex", headers=admin_headers)
    unindexed = _upload(client, admin_headers, "Bulk unindexed")
    with SessionLocal() as db:
        db.get(KnowledgeDocument, unindexed).index_status = "failed"
        db.commit()

    res = client.post("/admin/documents/bulk-approve", headers=admin_headers,
                      json={"ids": [good, unindexed, "missing", good]})
    assert res.status_code == 200
    body = res.json()
    assert body["approved"] == [good]
    assert body["skipped"] == {unindexed: "not indexed", "missing": "not found"}
    docs = {d["id"]: d for d in client.get("/admin/documents", headers=admin_headers).json()}
    assert docs[good]["review_status"] == "approved" and docs[good]["active"] is True
    assert docs[unindexed]["review_status"] != "approved"


def test_bulk_approve_requires_admin(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.post("/admin/documents/bulk-approve", headers=auth_headers, json={"ids": ["x"]}).status_code == 403


def test_approving_ingested_documents_activates_held_back_rows(client: TestClient, admin_headers: dict[str, str], monkeypatch) -> None:
    monkeypatch.setattr(ingest_module, "embed_text", lambda text, api_key=None: [0.1, 0.2, 0.3])
    with SessionLocal() as db:
        ingest_module.ingest_seed_yaml(db, api_key="fake", dry_run=False)
        assert db.query(FoodItem).filter(FoodItem.active.is_(True)).count() == 0
        assert db.query(Guideline).filter(Guideline.status == "active").count() == 0
        ids = [d.id for d in db.query(KnowledgeDocument).all()]

    res = client.post("/admin/documents/bulk-approve", headers=admin_headers, json={"ids": ids})
    assert len(res.json()["approved"]) == len(ids)

    with SessionLocal() as db:
        assert db.query(FoodItem).filter(FoodItem.active.is_(True)).count() == 5
        assert db.query(Guideline).filter(Guideline.status == "active").count() == 1
