from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings

PREVIOUS_REVISION = "8a4c6e2f901b"
M1C_REVISION = "9b5d7f3a102c"
INCIDENT_TABLES = {
    "incidents",
    "incident_evidence",
    "incident_hypotheses",
    "incident_diagnoses",
    "incident_audit_events",
    "incident_action_links",
}


def test_m1c_schema_upgrade_downgrade_and_second_upgrade(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "m1c-migration.db"
    database_url = f"sqlite:///{database}"
    monkeypatch.setenv("OPSPILOT_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PREVIOUS_REVISION)
    assert not INCIDENT_TABLES & set(inspect(create_engine(database_url)).get_table_names())

    command.upgrade(config, M1C_REVISION)
    upgraded = inspect(create_engine(database_url))
    assert set(upgraded.get_table_names()) >= INCIDENT_TABLES
    assert {column["name"] for column in upgraded.get_columns("incidents")} >= {
        "version",
        "status",
        "severity",
        "tags",
    }

    command.downgrade(config, PREVIOUS_REVISION)
    assert not INCIDENT_TABLES & set(inspect(create_engine(database_url)).get_table_names())

    command.upgrade(config, M1C_REVISION)
    assert set(inspect(create_engine(database_url)).get_table_names()) >= INCIDENT_TABLES
    get_settings.cache_clear()
