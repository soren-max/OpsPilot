from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings

PREVIOUS_REVISION = "d9f1a3b5274c"
M9_REVISION = "e0a2b4c6d8f0"


def test_m9_fresh_existing_and_round_trip(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'm9-migration.db'}"
    monkeypatch.setenv("OPSPILOT_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, PREVIOUS_REVISION)
    command.upgrade(config, M9_REVISION)
    tables = inspect(create_engine(database_url)).get_table_names()
    assert {"change_records", "change_outbox", "git_event_inbox"}.issubset(tables)
    command.downgrade(config, PREVIOUS_REVISION)
    assert "change_records" not in inspect(create_engine(database_url)).get_table_names()
    command.upgrade(config, "head")
    assert "change_outbox" in inspect(create_engine(database_url)).get_table_names()
    get_settings.cache_clear()
