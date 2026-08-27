from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings

PREVIOUS_REVISION = "c8e0f2a4163b"
M8_REVISION = "d9f1a3b5274c"


def test_m8_fresh_existing_and_round_trip(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'm8-migration.db'}"
    monkeypatch.setenv("OPSPILOT_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PREVIOUS_REVISION)
    assert "execution_records" not in inspect(create_engine(database_url)).get_table_names()
    command.upgrade(config, M8_REVISION)
    tables = inspect(create_engine(database_url)).get_table_names()
    assert {"execution_records", "execution_outbox"}.issubset(tables)
    command.downgrade(config, PREVIOUS_REVISION)
    assert "execution_records" not in inspect(create_engine(database_url)).get_table_names()
    command.upgrade(config, "head")
    assert "execution_outbox" in inspect(create_engine(database_url)).get_table_names()
    get_settings.cache_clear()
