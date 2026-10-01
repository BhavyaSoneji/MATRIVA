from fastapi.testclient import TestClient

from app.services.resources import search_resources


def test_resources_require_auth(client: TestClient) -> None:
    assert client.get("/resources").status_code in (401, 403)


def test_library_is_substantial_and_well_formed(client: TestClient, auth_headers) -> None:
    body = client.get("/resources?limit=60", headers=auth_headers).json()
    assert len(body["resources"]) >= 50
    assert {"video", "article", "guideline", "research"} >= {r["type"] for r in body["resources"]}
    for item in body["resources"]:
        assert item["url"].startswith("https://")
        assert item["topic"] in body["topics"]
        if item["type"] == "video":
            assert "youtube.com/watch?v=" in item["url"]


def test_topic_and_type_filters(client: TestClient, auth_headers) -> None:
    body = client.get("/resources?topic=ayurveda&type=video", headers=auth_headers).json()
    assert body["resources"], "expected curated Ayurveda videos"
    assert all(r["topic"] == "ayurveda" and r["type"] == "video" for r in body["resources"])


def test_query_ranks_relevant_and_off_topic_returns_nothing() -> None:
    hits = search_resources(query="yoga during pregnancy", limit=5)
    assert hits and any("yoga" in h["title"].lower() for h in hits)
    assert search_resources(query="zzzxqv qqwwee") == []


def test_stage_filter_excludes_other_stages() -> None:
    for item in search_resources(topic="labour", stage="1", limit=20):
        assert "all" in item["stages"] or "1" in item["stages"]
