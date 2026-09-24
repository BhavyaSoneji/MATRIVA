"""SQLAlchemy ORM model for knowledge_chunks (issue #5).

Maps to the `knowledge_chunks` table (Master Prompt Section 8), storing the
Section 15 embedding-pipeline output: embedding + content + metadata + source
reference. Requires the pgvector Postgres extension (docker-compose.yml
already uses the `pgvector/pgvector:pg16` image).
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

EMBEDDING_DIM = 768  # Gemini text-embedding-004 output dimension


class KnowledgeChunkRecord(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    document_id: Mapped[str] = mapped_column(String, index=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    pregnancy_stage: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    evidence_level: Mapped[str] = mapped_column(String, index=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    language: Mapped[str] = mapped_column(String, default="en")
    content: Mapped[str] = mapped_column(String)
    chunk_index: Mapped[int] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
