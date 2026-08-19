from pathlib import Path

from fastapi.testclient import TestClient

from app.core.command_profiles import CommandAction, CommandProfile
from app.core.config import get_settings


def test_health_is_liveness_only(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()["data"]
    assert body == {"status": "ok", "application": "responsive"}
    assert client.get("/health").json()["data"] == body


def test_ready_reports_mock_dependencies_without_execution(client: TestClient) -> None:
    body = client.get("/api/v1/ready").json()["data"]
    assert body["status"] == "ready"
    assert body["database"] == "available"
    assert body["worker"]["status"] == "configured"
    assert body["executor"]["type"] == "mock"
    assert body["services"]["required"] is False


def test_ready_reports_pending_local_services_without_running_it(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    script = tmp_path / "services.sh"
    script.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    script.chmod(0o755)
    configured = get_settings()
    monkeypatch.setattr(configured, "executor_type", "local_services")
    monkeypatch.setattr(configured, "services_script_path", str(script))
    monkeypatch.setattr(configured, "services_working_directory", str(tmp_path))
    monkeypatch.setattr(configured, "services_command_profile", "pending-confirmation")
    body = client.get("/api/v1/ready").json()["data"]
    assert body["status"] == "not_ready"
    checks = body["services"]["preflight"]["checks"]
    assert checks["script_exists"]["status"] == "ok"
    assert checks["script_executable"]["status"] == "ok"
    assert checks["command_profile"]["status"] == "failed"
    assert "does not exist" in checks["command_profile"]["reason"]


def test_ready_reports_missing_and_non_executable_script_metadata(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    configured = get_settings()
    monkeypatch.setattr(configured, "executor_type", "local_services")
    monkeypatch.setattr(configured, "services_working_directory", str(tmp_path))
    monkeypatch.setattr(configured, "services_command_profile", "confirmed-test-profile")
    monkeypatch.setattr(configured, "services_script_path", str(tmp_path / "missing-services.sh"))
    missing = client.get("/ready").json()["data"]
    assert missing["status"] == "not_ready"
    checks = missing["services"]["preflight"]["checks"]
    assert checks["script_exists"]["status"] == "failed"
    assert "does not exist" in checks["script_exists"]["reason"]

    script = tmp_path / "services.sh"
    script.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    script.chmod(0o644)
    monkeypatch.setattr(configured, "services_script_path", str(script))
    not_executable = client.get("/ready").json()["data"]
    assert not_executable["status"] == "not_ready"
    checks = not_executable["services"]["preflight"]["checks"]
    assert checks["script_exists"]["status"] == "ok"
    assert checks["script_executable"]["status"] == "failed"


def test_ready_passes_complete_status_only_local_services_preflight(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    script = tmp_path / "services.sh"
    script.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    script.chmod(0o755)
    configured = get_settings()
    profile = CommandProfile(
        capabilities=["status", "start", "stop"],
        parser="json_status",
        actions={
            action: CommandAction(argv=[action, "{environment}", "{host}", "{service}"])
            for action in ("status", "start", "stop")
        },
    )
    values = {
        "executor_type": "local_services",
        "environment": "test-mock",
        "environment_mode": "integration-test",
        "dry_run_only": False,
        "execution_acknowledged": True,
        "write_operations_enabled": False,
        "production_operations_enabled": False,
        "services_script_path": str(script),
        "services_working_directory": str(tmp_path),
        "services_command_profile": "confirmed-v1",
        "command_profiles": {"confirmed-v1": profile},
        "allowed_environments": "test-mock",
        "allowed_hosts": "mock-host-ok",
        "allowed_services": "mock-service",
        "allowed_actions": "status",
    }
    for name, value in values.items():
        monkeypatch.setattr(configured, name, value)

    body = client.get("/ready").json()["data"]
    assert body["status"] == "ready"
    checks = body["services"]["preflight"]["checks"]
    assert all(item["status"] == "ok" for item in checks.values())


def test_ready_accepts_dynamic_profile_without_bootstrap_command_profile_check(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    script = tmp_path / "ssh-wrapper.sh"
    script.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    script.chmod(0o755)
    configured = get_settings()
    values = {
        "executor_type": "local_services",
        "environment_mode": "integration-test",
        "dry_run_only": False,
        "execution_acknowledged": True,
        "write_operations_enabled": False,
        "production_operations_enabled": False,
        "allowed_actions": "status",
        "services_script_path": str(script),
        "services_working_directory": str(tmp_path),
    }
    for name, value in values.items():
        monkeypatch.setattr(configured, name, value)
    monkeypatch.setattr(
        "app.api.routes.system.dynamic_configuration_readiness",
        lambda _db, _settings: {"status": "ready", "checks": {}},
    )

    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ready"
    assert body["services"]["command_profile"] == "configured"
    assert body["services"]["profile_name"] == "dynamic-operations"


def test_ready_rejects_script_symlink_with_specific_reason(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    target = tmp_path / "target.sh"
    target.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    target.chmod(0o755)
    link = tmp_path / "services.sh"
    link.symlink_to(target)
    configured = get_settings()
    monkeypatch.setattr(configured, "executor_type", "local_services")
    monkeypatch.setattr(configured, "services_script_path", str(link))
    monkeypatch.setattr(configured, "services_working_directory", str(tmp_path))
    checks = client.get("/ready").json()["data"]["services"]["preflight"]["checks"]
    assert checks["script_not_symlink"] == {
        "status": "failed",
        "reason": "services script must exist and symlinks are forbidden",
    }
