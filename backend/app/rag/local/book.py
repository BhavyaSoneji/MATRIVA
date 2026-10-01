"""Knowledge representation of the Prasuti Tantra: outline, bilingual glossary, concepts and authorities.

The structure is recovered from the OCR by ingestion/pipelines/book_structure.py (see that module for how), and
`backend/scripts/build_book_index.py` writes it to `app/data/book_index.json`. This module only reads that file, so
the API, the chat and the Hindi-query glossary share one representation. Nothing here uses a model or the network.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Any

from app.rag.local.text import fold

INDEX_PATH = Path(__file__).resolve().parents[2] / "data" / "book_index.json"
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


@functools.lru_cache(maxsize=1)
def load_index() -> dict[str, Any] | None:
    if not INDEX_PATH.exists():
        return None
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def reset_cache() -> None:
    load_index.cache_clear()


def outline() -> dict[str, Any]:
    """The book's outline and summary statistics (empty when the index has not been built)."""
    data = load_index()
    if data is None:
        return {"available": False, "chapters": [], "authorities": {}, "stats": {}}
    return {"available": True, **{k: v for k, v in data.items() if k != "glossary"}}


def search_glossary(query: str, limit: int = 12) -> list[dict[str, Any]]:
    """Hindi <-> English term pairs matching `query` (either script). Contents-sourced pairs rank first."""
    data = load_index()
    q = query.strip()
    if data is None or not q:
        return []
    needle = q if _DEVANAGARI.search(q) else fold(q)
    out = []
    for entry in data["glossary"]:
        hay = entry["hi"] if _DEVANAGARI.search(q) else fold(entry["en"])
        if needle in hay:
            out.append(entry)
    out.sort(key=lambda e: (e["source"] != "contents", -e["count"], len(e["en"])))
    return out[:limit]


def hindi_terms_to_english(min_hi_chars: int = 4) -> dict[str, str]:
    """{Hindi phrase: English words} drawn from the glossary, for translating Hindi questions offline."""
    data = load_index()
    if data is None:
        return {}
    pairs: dict[str, str] = {}
    for e in data["glossary"]:
        if len(e["hi"]) < min_hi_chars or (e["source"] == "body" and e["count"] < 3):
            continue
        words = [w for w in re.findall(r"[a-z]{3,}", fold(e["en"])) if w not in {"and", "the", "for", "with", "its", "during"}]
        if words:
            pairs[e["hi"]] = " ".join(words[:5])
    return pairs
