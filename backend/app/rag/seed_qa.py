"""Minimal retrieval + Groq generation for the Round 1 demo (issue #66).

Scoped-down version of #5/#6/#9: loads the hand-curated seed file (#65) into
memory, does simple keyword-overlap retrieval (no pgvector/embeddings yet),
and calls Groq with the source-grounded system prompt (Master Prompt Section 58).

Exposed as a plain callable (`answer_question`) so the backend's /chat endpoint
(#69) can import and call it directly - no service layer needed for Sprint 0.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from groq import Groq

from app.llm.prompts import SOURCE_GROUNDED_SYSTEM_PROMPT as SYSTEM_PROMPT
from app.rag.keyword_search import tokenize as _tokenize

SEED_PATH = Path(__file__).resolve().parents[3] / "knowledge" / "seed" / "seed.yaml"


@lru_cache
def load_seed() -> list[dict[str, Any]]:
    with SEED_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def retrieve(query: str, k: int = 4) -> list[dict[str, Any]]:
    """Simple keyword-overlap retrieval. Full hybrid retrieval lands in #6."""
    query_tokens = _tokenize(query)
    scored = []
    for entry in load_seed():
        entry_tokens = _tokenize(f"{entry['title']} {entry['content']} {entry['topic']}")
        overlap = len(query_tokens & entry_tokens)
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:k]]


def _build_context(entries: list[dict[str, Any]]) -> str:
    blocks = []
    for e in entries:
        blocks.append(
            f"[{e['document_id']}] domain={e['domain']} evidence_level={e['evidence_level']} "
            f"review_status={e['review_status']} source={e['source_id']}\n"
            f"title: {e['title']}\n"
            f"content: {e['content'].strip()}"
        )
    return "\n\n".join(blocks)


def _evidence_label(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "INSUFFICIENT_EVIDENCE"
    levels = {e["evidence_level"] for e in entries}
    pending_review = any(e["review_status"] == "PENDING_CLINICAL_REVIEW" for e in entries)
    if pending_review:
        return "MIXED_PENDING_CLINICAL_REVIEW" if len(levels) > 1 else "TRADITIONAL_PENDING_CLINICAL_REVIEW"
    if levels == {"SUPPORTED"}:
        return "SUPPORTED"
    if levels == {"TRADITIONAL"}:
        return "TRADITIONAL"
    return "MIXED_MODERN_TRADITIONAL"


def answer_question(
    query: str,
    *,
    api_key: str | None = None,
    model: str = "llama-3.3-70b-versatile",
) -> dict[str, Any]:
    """Return {answer, sources[], evidence_label} for a single demo question."""
    entries = retrieve(query)

    if not entries:
        return {
            "answer": (
                "I don't have grounded evidence in the current knowledge set to answer that. "
                "Please consult your antenatal care provider."
            ),
            "sources": [],
            "evidence_label": "INSUFFICIENT_EVIDENCE",
        }

    context = _build_context(entries)
    key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Groq API key not configured (set LLM_API_KEY or GROQ_API_KEY)")

    client = Groq(api_key=key)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Retrieved evidence:\n\n{context}\n\nQuestion: {query}",
            },
        ],
        temperature=0.2,
    )
    answer = completion.choices[0].message.content

    sources = [
        {
            "document_id": e["document_id"],
            "title": e["title"],
            "source_id": e["source_id"],
            "domain": e["domain"],
            "evidence_level": e["evidence_level"],
            "review_status": e["review_status"],
        }
        for e in entries
    ]

    return {
        "answer": answer,
        "sources": sources,
        "evidence_label": _evidence_label(entries),
    }


if __name__ == "__main__":
    demo_question = (
        "I'm in my second trimester - what should I eat, and are there any Ayurvedic "
        "diet recommendations for this stage?"
    )
    result = answer_question(demo_question)
    print(result)
