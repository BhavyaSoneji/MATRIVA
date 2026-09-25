"""add daily wellness logs table

Revision ID: 0003_daily_wellness_logs
Revises: 0002_rag_vector_index
"""
import sqlalchemy as sa

from alembic import op

revision = "0003_daily_wellness_logs"
down_revision = "0002_rag_vector_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_wellness_logs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("water_intake_ml", sa.Float(), nullable=True),
        sa.Column("sleep_hours", sa.Float(), nullable=True),
        sa.Column("activity_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "log_date", name="uq_wellness_user_date"),
    )
    op.create_index("ix_daily_wellness_logs_user_id", "daily_wellness_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_wellness_logs_user_id", table_name="daily_wellness_logs")
    op.drop_table("daily_wellness_logs")
