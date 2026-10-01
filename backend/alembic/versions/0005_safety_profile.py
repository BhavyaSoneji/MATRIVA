"""safety profile: current medicines, risk factors, age and blood group on the health profile

Revision ID: 0005_safety_profile
Revises: 0004_care_features
"""
import sqlalchemy as sa

from alembic import op

revision = "0005_safety_profile"
down_revision = "0004_care_features"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("current_medications", sa.JSON()),
    ("risk_factors", sa.JSON()),
    ("age_years", sa.Integer()),
    ("blood_group", sa.String(8)),
)


def upgrade() -> None:
    # A fresh database already has these columns (0001 runs create_all from the current models).
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("health_profiles")}
    for name, kind in _COLUMNS:
        if name not in existing:
            op.add_column("health_profiles", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("health_profiles")}
    for name, _ in _COLUMNS:
        if name in existing:
            op.drop_column("health_profiles", name)
