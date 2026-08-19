import pytest
from conftest import TestingSession
from sqlalchemy import select

from app import seed as seed_module
from app.core.config import Settings
from app.core.enums import OperationAction, OperationScope
from app.models import Environment, Host, OperationTask, Service


def integration_settings() -> Settings:
    return Settings(
        environment="sandbox-reviewed",
        environment_mode="integration-test",
        executor_type="local_services",
        dry_run_only=False,
        execution_acknowledged=True,
        write_operations_enabled=False,
        production_operations_enabled=False,
        services_script_path="/confirmed/services.sh",
        services_working_directory="/confirmed",
        services_command_profile="confirmed-v1",
        allowed_environments="sandbox-reviewed",
        allowed_hosts="reviewed-host",
        allowed_services="reviewed-service",
        allowed_actions="status",
        _env_file=None,
    )


def test_seed_reset_replaces_unreferenced_mock_catalog(monkeypatch) -> None:
    configured = integration_settings()
    monkeypatch.setattr(seed_module, "SessionLocal", TestingSession)
    monkeypatch.setattr(seed_module, "get_settings", lambda: configured)

    seed_module.seed(reset=True)

    with TestingSession() as db:
        assert set(db.scalars(select(Environment.code))) == {"sandbox-reviewed"}
        assert set(db.scalars(select(Host.name))) == {"reviewed-host"}
        assert set(db.scalars(select(Service.name))) == {"reviewed-service"}


def test_switch_to_integration_seeds_real_allowlist_alongside_old_mock(monkeypatch) -> None:
    configured = integration_settings()
    monkeypatch.setattr(seed_module, "SessionLocal", TestingSession)
    monkeypatch.setattr(seed_module, "get_settings", lambda: configured)

    seed_module.seed()

    with TestingSession() as db:
        assert set(db.scalars(select(Environment.code))) == {
            "test-mock",
            "disabled",
            "sandbox-reviewed",
        }
        assert "reviewed-host" in set(db.scalars(select(Host.name)))
        assert "reviewed-service" in set(db.scalars(select(Service.name)))


def test_seed_reset_refuses_catalog_referenced_by_history() -> None:
    with TestingSession() as db:
        environment = db.scalar(select(Environment).where(Environment.code == "test-mock"))
        assert environment is not None
        db.add(
            OperationTask(
                environment_id=environment.id,
                action=OperationAction.STATUS,
                scope=OperationScope.SERVICE_HOSTS,
                requested_by="test-user",
            )
        )
        db.commit()
        with pytest.raises(RuntimeError, match="operation/approval history"):
            seed_module._reset_catalog(db)


def test_seed_rejects_incomplete_existing_integration_catalog(monkeypatch) -> None:
    configured = integration_settings()
    monkeypatch.setattr(seed_module, "SessionLocal", TestingSession)
    monkeypatch.setattr(seed_module, "get_settings", lambda: configured)
    with TestingSession() as db:
        existing = db.scalar(select(Environment).where(Environment.code == "test-mock"))
        assert existing is not None
        existing.code = "sandbox-reviewed"
        db.commit()

    with pytest.raises(RuntimeError, match="does not match the configured allowlists"):
        seed_module.seed()
