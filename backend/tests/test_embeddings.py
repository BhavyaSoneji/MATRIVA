import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag import embeddings


def test_embed_text_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Gemini API key not configured"):
        embeddings.embed_text("hello")


def test_embed_text_calls_gemini_with_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    def fake_configure(api_key: str) -> None:
        calls["api_key"] = api_key

    def fake_embed_content(model: str, content: str, output_dimensionality: int) -> dict:
        calls["model"] = model
        calls["content"] = content
        calls["output_dimensionality"] = output_dimensionality
        return {"embedding": [0.1, 0.2, 0.3]}

    monkeypatch.setattr(embeddings.genai, "configure", fake_configure)
    monkeypatch.setattr(embeddings.genai, "embed_content", fake_embed_content)

    result = embeddings.embed_text("second trimester nutrition", api_key="test-key")

    assert result == [0.1, 0.2, 0.3]
    assert calls["api_key"] == "test-key"
    assert calls["content"] == "second trimester nutrition"
    assert calls["model"] == embeddings.EMBEDDING_MODEL
    assert calls["output_dimensionality"] == embeddings.EMBEDDING_DIM


def test_embed_chunk_contents_embeds_each_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embeddings.genai, "configure", lambda api_key: None)
    monkeypatch.setattr(
        embeddings.genai,
        "embed_content",
        lambda model, content, output_dimensionality: {"embedding": [len(content)]},
    )

    results = embeddings.embed_chunk_contents(["a", "bb", "ccc"], api_key="test-key")

    assert results == [[1], [2], [3]]
