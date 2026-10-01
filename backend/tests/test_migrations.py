from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


def test_alembic_upgrade_head_on_fresh_database(tmp_path: Path) -> None:
    """Regression for #79: later migrations must tolerate tables created by 0001."""

    backend_dir = Path(__file__).resolve().parents[1]
    database_path = (tmp_path / "fresh-migration.db").as_posix()
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{database_path}",
            "VECTOR_DATABASE_URL": f"sqlite:///{database_path}",
            "AUTO_CREATE_TABLES": "false",
            "ENVIRONMENT": "test",
            "DEMO_MODE": "true",
            "JWT_SECRET": "test-secret-with-at-least-32-characters",
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        engine.dispose()

    assert version == "0005_safety_profile"