"""add the RAG vector index table

Revision ID: 0002_rag_vector_index
Revises: 0001_initial
"""
from alembic import op

from app.models.knowledge import KnowledgeChunkRecord, RagBase

revision = "0002_rag_vector_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        RagBase.metadata.create_all(bind=bind, tables=[KnowledgeChunkRecord.__table__])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        RagBase.metadata.drop_all(bind=bind, tables=[KnowledgeChunkRecord.__table__])
