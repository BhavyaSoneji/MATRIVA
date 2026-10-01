"""Glue between the local RAG engine and the rest of the app (chat service, knowledge API)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.llm.generator import GenerationResult
from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource
from app.rag.local.composer import compose
from app.rag.local.corpus import get_engine
from app.rag.local.retriever import UserProfile, search
from app.rag.reranking import UserContext
from app.rag.retrieval import RetrievedChunk


def _profile(stage: str | None, region: str | None, context: UserContext | None) -> UserProfile:
    return UserProfile(
        stage=stage,
        region=region,
        diet=(context.diet or "").lower() or None if context else None,
        allergies=list(context.allergies) if context else [],
    )


def answer_local(
    db: Session,
    query: str,
    *,
    stage: str | None = None,
    region: str | None = None,
    profile: UserContext | None = None,
) -> tuple[GenerationResult, list[RetrievedChunk]]:
    """Retrieve, judge and compose. Returns the same shape as app.rag.pipeline.answer_question, with the
    retrieved chunks in citation order ([1] first). An empty result means "insufficient evidence"."""
    engine = get_engine(db)
    user = _profile(stage, region, profile)
    retrieval = search(engine, query, profile=user)
    if not retrieval.sufficient:
        trace = {"engine": "local", "confidence": retrieval.confidence, "reason": retrieval.reason,
                 "concepts": [engine.graph.concepts[c].label for c in retrieval.concepts],
                 "query_terms": retrieval.query_tokens, "passages": [], "passages_searched": retrieval.pool}
        return GenerationResult(text="", citation_ids=[], trace=trace), []

    composed = compose(engine, retrieval, user)
    chunks: list[RetrievedChunk] = []
    for hit in composed.used:
        chunk = db.get(KnowledgeChunk, hit.id)
        if chunk is None:
            continue
        document = db.get(KnowledgeDocument, chunk.document_id)
        source = db.get(KnowledgeSource, chunk.source_id)
        chunks.append(RetrievedChunk(chunk=chunk, document=document, source=source, score=hit.score))
    citation_ids = list(dict.fromkeys(item.source.id for item in chunks[:4]))
    return GenerationResult(text=composed.text, citation_ids=citation_ids, trace=composed.trace), chunks


def stream_pieces(text: str) -> Iterator[str]:
    """Split a composed answer into line-sized deltas whose concatenation is exactly `text`."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        yield line + ("\n" if i < len(lines) - 1 else "")
