"""initial MATRIVA schema

Revision ID: 0001_initial
Revises:
"""
from alembic import op

from app.core.db import Base
from app import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # The model metadata is the canonical schema definition.  This keeps the initial
    # migration compatible with both PostgreSQL/pgvector and SQLite used by tests.
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
