"""Gemini embedding pipeline backed by LangChain.

Production uses ``langchain-google-genai``; the legacy Google SDK path is kept
behind ``RAG_ORCHESTRATOR=native`` as a rollback seam for existing deployments
and deterministic regression tests.
"""

from __future__ import annotations

import os
from functools import lru_cache

import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import get_settings

# text-embedding-004 was retired; gemini-embedding-001 defaults to 3072
# dimensions, so output_dimensionality stays pinned to the pgvector column.
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768


def _resolve_api_key(api_key: str | None) -> str:
    key = (
        api_key
        or get_settings().embedding_api_key
        or os.environ.get("EMBEDDING_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    if not key:
        raise RuntimeError(
            "Gemini API key not configured (set EMBEDDING_API_KEY or GEMINI_API_KEY)"
        )
    return key


@lru_cache(maxsize=4)
def _langchain_embeddings(api_key: str, model: str) -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=model,
        api_key=api_key,
        output_dimensionality=EMBEDDING_DIM,
    )


def _use_langchain() -> bool:
    # Missing attributes on test/fake settings intentionally preserve the
    # legacy seam; real Settings always has the field and defaults to LangChain.
    return getattr(get_settings(), "rag_orchestrator", "native") == "langchain"


def embed_text(text: str, *, api_key: str | None = None, model: str = EMBEDDING_MODEL) -> list[float]:
    """Embed one query string through the configured LangChain provider."""

    key = _resolve_api_key(api_key)
    if _use_langchain():
        return _langchain_embeddings(key, model).embed_query(text)

    genai.configure(api_key=key)
    result = genai.embed_content(model=model, content=text, output_dimensionality=EMBEDDING_DIM)
    return result["embedding"]


def embed_chunk_contents(
    contents: list[str], *, api_key: str | None = None, model: str = EMBEDDING_MODEL
) -> list[list[float]]:
    """Embed document chunks through LangChain's batch document interface."""

    key = _resolve_api_key(api_key)
    if _use_langchain():
        return _langchain_embeddings(key, model).embed_documents(contents)

    return [embed_text(content, api_key=key, model=model) for content in contents]