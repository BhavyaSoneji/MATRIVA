"""Gemini embedding pipeline (issue #5, Master Prompt Section 15).

document -> clean -> normalize -> semantic chunk (#2-#3) -> embedding (here) -> pgvector (vector_store.py)
"""

from __future__ import annotations

import os

import google.generativeai as genai

EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIM = 768


def embed_text(text: str, *, api_key: str | None = None, model: str = EMBEDDING_MODEL) -> list[float]:
    """Embed a single string via the Gemini embedding API."""
    key = api_key or os.environ.get("EMBEDDING_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "Gemini API key not configured (set EMBEDDING_API_KEY or GEMINI_API_KEY)"
        )
    genai.configure(api_key=key)
    result = genai.embed_content(model=model, content=text)
    return result["embedding"]


def embed_chunk_contents(
    contents: list[str], *, api_key: str | None = None, model: str = EMBEDDING_MODEL
) -> list[list[float]]:
    """Embed multiple chunk contents. One API call per chunk -- batch embedding
    isn't exposed by this SDK version; batching can be added later if the
    Gemini API adds a true batch-embed endpoint."""
    return [embed_text(content, api_key=api_key, model=model) for content in contents]
