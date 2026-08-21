from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings

PREVIOUS_REVISION = "b7d9f1a3052e"
M4_REVISION = "c8e0f2a4163b"


def test_m4_fresh_existing_and_round_trip(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'm4-migration.db'}"
    monkeypatch.setenv("OPSPILOT_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PREVIOUS_REVISION)
    assert "approval_requests" not in inspect(create_engine(database_url)).get_table_names()
    command.upgrade(config, M4_REVISION)
    assert "approval_requests" in inspect(create_engine(database_url)).get_table_names()
    command.downgrade(config, PREVIOUS_REVISION)
    assert "approval_requests" not in inspect(create_engine(database_url)).get_table_names()
    command.upgrade(config, "head")
    assert "approval_requests" in inspect(create_engine(database_url)).get_table_names()
    get_settings.cache_clear()
