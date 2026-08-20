from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings

PREVIOUS_REVISION = "a6c8e0f2143d"
M3B_REVISION = "b7d9f1a3052e"


def test_m3b_schema_upgrade_downgrade_and_second_upgrade(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'm3b-migration.db'}"
    monkeypatch.setenv("OPSPILOT_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PREVIOUS_REVISION)
    before = set(inspect(create_engine(database_url)).get_table_names())
    command.upgrade(config, M3B_REVISION)
    assert set(inspect(create_engine(database_url)).get_table_names()) == before
    command.downgrade(config, PREVIOUS_REVISION)
    command.upgrade(config, M3B_REVISION)
    assert set(inspect(create_engine(database_url)).get_table_names()) == before
    get_settings.cache_clear()
