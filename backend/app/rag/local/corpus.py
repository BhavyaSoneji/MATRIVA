"""Load the approved knowledge base into a searchable index, and keep it fresh.

Only what the retrieval gate already allows is indexed: active, approved documents whose source is
approved, and (for guidelines) only active, non-stale ones. So the local engine can never surface
anything the rest of the system would hide.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource, ReviewStatus
from app.rag.local.graph import KnowledgeGraph
from app.rag.local.index import LocalIndex, Passage
from app.rag.local.text import tokens


class Engine:
    """An index and the graph built from the same passages."""

    def __init__(self, passages: list[Passage]) -> None:
        self.index = LocalIndex(passages)
        self.graph = KnowledgeGraph.build([p.tokens for p in passages])
        self.by_id = {p.id: i for i, p in enumerate(passages)}


_lock = threading.Lock()
_cached: tuple[tuple[Any, ...], Engine] | None = None


def _approved_filter():
    return (
        KnowledgeDocument.active.is_(True),
        KnowledgeDocument.review_status == ReviewStatus.APPROVED.value,
        KnowledgeSource.review_status == ReviewStatus.APPROVED.value,
    )


def _signature(db: Session) -> tuple[Any, ...]:
    """Cheap fingerprint of the approved corpus: changes whenever a document is approved, rejected,
    reindexed or edited, so the cached index is rebuilt exactly when needed."""
    docs, newest = db.execute(
        select(func.count(KnowledgeDocument.id), func.max(KnowledgeDocument.updated_at))
        .join(KnowledgeSource, KnowledgeDocument.source_id == KnowledgeSource.id)
        .where(*_approved_filter())
    ).one()
    chunks = db.execute(
        select(func.count(KnowledgeChunk.id))
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .join(KnowledgeSource, KnowledgeDocument.source_id == KnowledgeSource.id)
        .where(*_approved_filter())
    ).scalar_one()
    return (docs, str(newest), chunks)


def load_passages(db: Session) -> list[Passage]:
    rows = db.execute(
        select(KnowledgeChunk, KnowledgeDocument, KnowledgeSource)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
        .where(*_approved_filter())
        .order_by(KnowledgeDocument.id, KnowledgeChunk.chunk_index)
    ).all()
    today = datetime.now(timezone.utc).date()
    passages: list[Passage] = []
    for chunk, document, source in rows:
        guideline = source.guideline
        if guideline is not None and (
            guideline.status != "active" or (guideline.review_due_date is not None and guideline.review_due_date < today)
        ):
            continue
        extra = chunk.extra_metadata or {}
        title = document.title
        passages.append(
            Passage(
                id=chunk.id,
                text=chunk.content,
                tokens=tokens(f"{chunk.content} {title} {source.topic or ''}"),
                meta={
                    "title": title,
                    "document_id": document.id,
                    "source_id": source.id,
                    "source_name": source.name,
                    "source_title": source.title,
                    "source_type": source.source_type,
                    "authority": source.authority,
                    "url": source.url,
                    "domain": document.domain,
                    "topic": source.topic,
                    "stage": document.pregnancy_stage,
                    "region": document.region,
                    "evidence_level": source.evidence_level,
                    "locator": extra.get("page_or_section"),
                    "readability": (extra.get("ocr_quality") or {}).get("readability", 1.0),
                },
            )
        )
    return passages


def get_engine(db: Session) -> Engine:
    """The current engine, rebuilt only when the approved corpus changed."""
    global _cached
    sig = _signature(db)
    with _lock:
        if _cached is None or _cached[0] != sig:
            _cached = (sig, Engine(load_passages(db)))
        return _cached[1]


def reset_cache() -> None:
    global _cached
    with _lock:
        _cached = None
