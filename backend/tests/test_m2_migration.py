from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings

PREVIOUS_REVISION = "9b5d7f3a102c"
M2_REVISION = "a6c8e0f2143d"
WORKFLOW_TABLES = {"workflow_runs", "workflow_evaluation_records"}


def test_m2_schema_upgrade_downgrade_and_second_upgrade(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "m2-migration.db"
    database_url = f"sqlite:///{database}"
    monkeypatch.setenv("OPSPILOT_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PREVIOUS_REVISION)
    assert not WORKFLOW_TABLES & set(inspect(create_engine(database_url)).get_table_names())

    command.upgrade(config, M2_REVISION)
    upgraded = inspect(create_engine(database_url))
    assert set(upgraded.get_table_names()) >= WORKFLOW_TABLES
    assert {column["name"] for column in upgraded.get_columns("workflow_runs")} >= {
        "incident_id",
        "status",
        "started_at",
        "finished_at",
        "last_checkpoint_at",
        "last_error",
    }

    command.downgrade(config, PREVIOUS_REVISION)
    assert not WORKFLOW_TABLES & set(inspect(create_engine(database_url)).get_table_names())
    command.upgrade(config, M2_REVISION)
    assert set(inspect(create_engine(database_url)).get_table_names()) >= WORKFLOW_TABLES
    get_settings.cache_clear()
