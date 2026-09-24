import json

from fastapi.testclient import TestClient


def test_admin_document_review_gate_and_audit(client: TestClient, admin_headers: dict[str, str]) -> None:
    metadata = {
        "title": "Reviewed test nutrition source",
        "domain": "nutrition",
        "source_name": "test-source",
        "source_type": "government",
        "authority": "Test authority",
        "evidence_level": "supported",
    }
    response = client.post(
        "/admin/documents",
        headers=admin_headers,
        data={"metadata": json.dumps(metadata)},
        files={"file": ("source.txt", b"Reviewed test source about balanced meals.", "text/plain")},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["active"] is False

    approved_before_index = client.post(f"/admin/documents/{document['id']}/approve", headers=admin_headers)
    assert approved_before_index.status_code == 409

    reindexed = client.post(f"/admin/documents/{document['id']}/reindex", headers=admin_headers)
    assert reindexed.status_code == 200
    approved = client.post(f"/admin/documents/{document['id']}/approve", headers=admin_headers)
    assert approved.status_code == 200
    assert approved.json()["active"] is True

    audit = client.get("/admin/audit-logs", headers=admin_headers)
    assert audit.status_code == 200
    assert any(item["action"] == "document.approve" for item in audit.json())


def test_export_and_delete_account(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.put("/profile", headers=auth_headers, json={"consent": True, "region": "Gujarat"})
    client.put("/pregnancy", headers=auth_headers, json={"current_week": 20})
    exported = client.get("/privacy/export", headers=auth_headers)
    assert exported.status_code == 200
    assert exported.json()["profile"]["consent"] is True
    assert exported.json()["pregnancy"]["current_week"] == 20
    deleted = client.delete("/privacy/account", headers=auth_headers)
    assert deleted.status_code == 200
    assert client.get("/profile", headers=auth_headers).status_code == 401
