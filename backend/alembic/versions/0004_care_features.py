"""care features: pregnancy dating, emergency contact, check-ins, readings, meals, screening

Revision ID: 0004_care_features
Revises: 0003_daily_wellness_logs
"""
import sqlalchemy as sa

from alembic import op

revision = "0004_care_features"
down_revision = "0003_daily_wellness_logs"
branch_labels = None
depends_on = None


def _create_table(name: str, *columns: sa.Column) -> None:
    op.create_table(name, *columns)


def _create_index(name: str, table: str, columns: list[str]) -> None:
    op.create_index(name, table, columns)


def upgrade() -> None:
    # 0001 uses Base.metadata.create_all(), which already materializes the current
    # model set on a fresh database. These guards keep the chain safe for both a
    # fresh install and a database created before these tables existed.
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "pregnancy_dating" not in existing:
        _create_table(
            "pregnancy_dating",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("lmp_date", sa.Date()),
            sa.Column("edd_date", sa.Date()),
            sa.Column("source", sa.String(12), nullable=False),
            sa.Column("pre_pregnancy_weight_kg", sa.Float()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "emergency_contacts" not in existing:
        _create_table(
            "emergency_contacts",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("phone", sa.String(32), nullable=False),
            sa.Column("relation", sa.String(60)),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "daily_checkins" not in existing:
        _create_table(
            "daily_checkins",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("check_date", sa.Date(), nullable=False),
            sa.Column("mood", sa.Integer()),
            sa.Column("symptoms", sa.JSON()),
            sa.Column("baby_movement", sa.String(20)),
            sa.Column("ifa_taken", sa.Boolean()),
            sa.Column("note", sa.Text()),
            sa.Column("red_flags", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "check_date", name="uq_checkin_user_date"),
        )
        _create_index("ix_daily_checkins_user_id", "daily_checkins", ["user_id"])

    if "health_readings" not in existing:
        _create_table(
            "health_readings",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("reading_date", sa.Date(), nullable=False),
            sa.Column("value", sa.Float()),
            sa.Column("systolic", sa.Integer()),
            sa.Column("diastolic", sa.Integer()),
            sa.Column("context", sa.String(30)),
            sa.Column("note", sa.Text()),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        _create_index("ix_health_readings_user_id", "health_readings", ["user_id"])
        _create_index("ix_readings_user_kind_date", "health_readings", ["user_id", "kind", "reading_date"])

    if "meal_logs" not in existing:
        _create_table(
            "meal_logs",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("meal_date", sa.Date(), nullable=False),
            sa.Column("meal_type", sa.String(20)),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("items", sa.JSON()),
            sa.Column("totals", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        _create_index("ix_meal_logs_user_id", "meal_logs", ["user_id"])
        _create_index("ix_meal_logs_meal_date", "meal_logs", ["meal_date"])

    if "screening_records" not in existing:
        _create_table(
            "screening_records",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("week", sa.Integer()),
            sa.Column("level", sa.String(20), nullable=False),
            sa.Column("flagged", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        _create_index("ix_screening_records_user_id", "screening_records", ["user_id"])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in (
        "screening_records",
        "meal_logs",
        "health_readings",
        "daily_checkins",
        "emergency_contacts",
        "pregnancy_dating",
    ):
        if table in existing:
            op.drop_table(table)