from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings

PREVIOUS_REVISION = "7f3b55c910d4"
M1B_REVISION = "8a4c6e2f901b"
LEGACY_TARGET_COLUMNS = {
    "address",
    "ssh_port",
    "ssh_username",
    "credential_reference",
}


def test_m1b_schema_upgrade_and_downgrade_round_trip(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "migration.db"
    database_url = f"sqlite:///{database}"
    monkeypatch.setenv("OPSPILOT_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PREVIOUS_REVISION)
    before = inspect(create_engine(database_url))
    assert {
        column["name"] for column in before.get_columns("hosts")
    } >= LEGACY_TARGET_COLUMNS
    assert before.has_table("operations_integration_configs")

    command.upgrade(config, M1B_REVISION)
    upgraded = inspect(create_engine(database_url))
    upgraded_columns = {column["name"] for column in upgraded.get_columns("hosts")}
    assert not LEGACY_TARGET_COLUMNS & upgraded_columns
    assert "labels" in upgraded_columns
    assert not upgraded.has_table("operations_integration_configs")

    command.downgrade(config, PREVIOUS_REVISION)
    downgraded = inspect(create_engine(database_url))
    downgraded_columns = {column["name"] for column in downgraded.get_columns("hosts")}
    assert downgraded_columns >= LEGACY_TARGET_COLUMNS
    assert "labels" not in downgraded_columns
    assert downgraded.has_table("operations_integration_configs")
    get_settings.cache_clear()
