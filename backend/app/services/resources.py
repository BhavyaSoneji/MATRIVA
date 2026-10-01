"""Curated resource library (videos, articles, guidelines, research papers).

Backed by backend/app/data/library.yaml, which `knowledge/resources/build_library.py`
generates and live-verifies. These are pointers to real third-party material --
the chat UI shows them next to answers -- and are deliberately separate from the
reviewed knowledge base that grounds answers (see app.rag.retrieval).
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

from app.rag.local.text import tokens

# Same idea as retrieval.MIN_KEYWORD_RELEVANCE: one incidental shared word ("doctor") out of five
# meaningful query words must not attach an unrelated video to an answer.
_MIN_QUERY_OVERLAP = 0.3


def tokenize(text: str) -> set[str]:
    return set(tokens(text))

_LIBRARY_PATH = Path(__file__).resolve().parents[1] / "data" / "library.yaml"


@functools.lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with _LIBRARY_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    topics: dict[str, str] = data.get("topics", {})
    resources = []
    for raw in data.get("resources", []):
        item = dict(raw)
        item["stages"] = [s.strip() for s in str(item.get("stages", "all")).split(",") if s.strip()]
        item["_tokens"] = tokenize(
            f"{item['title']} {item.get('about', '')} {item['topic']} {topics.get(item['topic'], '')}"
        )
        resources.append(item)
    return {"verified_on": str(data["verified_on"]) if data.get("verified_on") else None, "topics": topics, "resources": resources}


def topics() -> dict[str, str]:
    return dict(_load()["topics"])


def verified_on() -> str | None:
    return _load()["verified_on"]


def _stage_key(stage: str | None) -> str | None:
    return stage.strip() if stage and stage.strip() else None


def search_resources(
    *,
    query: str = "",
    topic: str | None = None,
    resource_type: str | None = None,
    stage: str | None = None,
    language: str | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Filter by topic/type/stage/language, then rank by overlap with the query.

    With no query the original curated order is kept, so a bare topic filter
    behaves like browsing a shelf. A query whose overlap is below the relevance floor
    returns [] so the chat never attaches unrelated links to an answer.
    """
    stage = _stage_key(stage)
    q_tokens = tokenize(query) if query.strip() else set()
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for index, item in enumerate(_load()["resources"]):
        if topic and item["topic"] != topic:
            continue
        if resource_type and item["type"] != resource_type:
            continue
        if language and item.get("language") != language:
            continue
        if stage and "all" not in item["stages"] and stage not in item["stages"]:
            continue
        score = 0.0
        if q_tokens:
            score = len(q_tokens & item["_tokens"]) / len(q_tokens)
            if score < _MIN_QUERY_OVERLAP:
                continue
        scored.append((score, index, item))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [{k: v for k, v in item.items() if not k.startswith("_")} for _, _, item in scored[:limit]]
