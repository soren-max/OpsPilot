from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import IntegrationConfigStatus, OperationAction, TargetStatus
from app.core.security import hash_password
from app.executors.base import ExecutionResult, ExecutionTarget
from app.integration_schemas import IntegrationConfigInput
from app.models import AuditLog, Environment, Host, OperationsIntegrationConfig, Service, User
from app.services.integration_config import (
    all_configured_tests_passed,
    build_config_executor,
    list_credentials,
    save_config,
    store_credential,
    validate_config,
)
from app.services.integration_config import (
    test_status as run_status_test,
)
from app.services.readiness import dynamic_configuration_readiness

ENVIRONMENT_ID = "00000000-0000-0000-0000-000000000001"
HOST_ID = "10000000-0000-0000-0000-000000000001"
SERVICE_ID = "20000000-0000-0000-0000-000000000001"


def payload() -> dict[str, object]:
    return {
        "environment": {"name": "测试模拟环境", "code": "test-mock", "level": "TEST"},
        "hosts": [
            {
                "id": HOST_ID,
                "name": "mock-host-ok",
                "address": "127.0.0.1",
                "ssh_port": 22,
                "ssh_username": "opspilot",
                "credential_reference": "ops-key-01",
            }
        ],
        "services": [{"id": SERVICE_ID, "name": "mock-service", "host_names": ["mock-host-ok"]}],
        "execution": {
            "services_sh_remote_path": "/opt/opspilot/services.sh",
            "working_directory": "/opt/opspilot",
            "timeout_seconds": 10,
            "status_argv": ["status", "{environment}", "{host}", "{service}"],
        },
        "parser": {
            "type": "regex",
            "exit_code_map": {"255": "unreachable"},
            "stdout_regex": {"running": "running", "stopped": "stopped"},
            "stderr_regex": {"failed": "failed", "unreachable": "unreachable"},
            "conflict_policy": "failed",
            "default_state": "unknown",
            "custom_parser": None,
        },
        "allowlist": {
            "environments": ["test-mock"],
            "hosts": ["mock-host-ok"],
            "services": ["mock-service"],
            "actions": ["status"],
        },
    }


def test_config_api_save_is_draft_audited_and_never_accepts_secret(client, db) -> None:
    saved = client.put(f"/api/v1/admin/operations-integration/{ENVIRONMENT_ID}", json=payload())
    assert saved.status_code == 200
    body = saved.json()["data"]
    assert body["status"] == "DRAFT"
    assert body["enabled"] is False
    assert body["hosts"][0]["credential_reference"] == "ops-key-01"
    assert "private_key" not in str(body)
    audit = db.scalar(select(AuditLog).where(AuditLog.event_type == "INTEGRATION_CONFIG_SAVED"))
    assert audit is not None
    rejected = payload()
    rejected["private_key"] = "forbidden"
    response = client.put(f"/api/v1/admin/operations-integration/{ENVIRONMENT_ID}", json=rejected)
    assert response.status_code == 422


def test_config_api_can_create_first_environment_without_seeded_site_contract(client, db) -> None:
    body = payload()
    body["environment"] = {
        "name": "New reviewed environment",
        "code": "reviewed-new",
        "level": "TEST",
    }
    body["allowlist"]["environments"] = ["reviewed-new"]
    body["hosts"][0].pop("id")
    body["services"][0].pop("id")
    created = client.post("/api/v1/admin/operations-integration", json=body)
    assert created.status_code == 201
    assert created.json()["data"]["status"] == "DRAFT"
    assert db.scalar(select(Environment).where(Environment.code == "reviewed-new")) is not None


def test_config_api_requires_config_write_permission(client, db) -> None:
    db.add(
        User(
            username="readonly-config-user",
            display_name="Read only",
            password_hash=hash_password("readonly-test-password"),
            enabled=True,
            status="ACTIVE",
        )
    )
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "readonly-config-user", "password": "readonly-test-password"},
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    response = client.put(f"/api/v1/admin/operations-integration/{ENVIRONMENT_ID}", json=payload())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_invalid_credential_is_never_reflected_by_validation_response(client) -> None:
    secret_value = "-----BEGIN " + "PRIVATE KEY-----short-secret-value"
    response = client.post(
        "/api/v1/admin/operations-integration/credentials",
        json={"name": "bad-key", "private_key": secret_value},
    )
    assert response.status_code == 422
    assert secret_value not in response.text


def test_credential_store_returns_metadata_only_and_uses_0600(tmp_path) -> None:
    credential_root = tmp_path / "ssh"
    credential_root.mkdir(mode=0o700)
    settings = Settings(
        secret_key="test-only-secret-key-not-for-deployment",
        credential_directory=str(credential_root),
        _env_file=None,
    )
    private_key = (
        "-----BEGIN " + "PRIVATE KEY-----\n" + ("A" * 96) + "\n-----END PRIVATE KEY-----\n"
    )
    metadata = store_credential(settings, "ops-key-safe", private_key)
    assert metadata["name"] == "ops-key-safe"
    assert metadata["configured"] is True
    assert private_key not in str(metadata)
    assert (credential_root / "ops-key-safe").stat().st_mode & 0o777 == 0o600
    assert private_key not in str(list_credentials(settings))


def configured_settings(tmp_path: Path, wrapper: Path) -> Settings:
    credential = tmp_path / "ops-key-01"
    credential.write_text("fixture-private-key", encoding="utf-8")
    credential.chmod(0o600)
    (tmp_path / "known_hosts").write_text("fixture known host\n", encoding="utf-8")
    return Settings(
        secret_key="test-only-secret-key-not-for-deployment",
        environment_mode="integration-test",
        executor_type="local_services",
        dry_run_only=False,
        execution_acknowledged=True,
        production_operations_enabled=False,
        services_script_path=str(wrapper),
        services_working_directory=str(tmp_path),
        credential_directory=str(tmp_path),
        ssh_known_hosts_path=str(tmp_path / "known_hosts"),
        allowed_environments="test-mock",
        allowed_hosts="mock-host-ok",
        allowed_services="mock-service",
        allowed_actions="status",
        services_command_profile="bootstrap-wrapper",
        _env_file=None,
    )


def save_fixture_config(db) -> OperationsIntegrationConfig:
    environment = db.get(Environment, ENVIRONMENT_ID)
    assert environment is not None
    return save_config(db, environment, IntegrationConfigInput.model_validate(payload()))


def test_validation_is_fail_closed_then_validates_complete_bootstrap(db, tmp_path) -> None:
    wrapper = tmp_path / "ssh-wrapper.sh"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    config = save_fixture_config(db)
    incomplete = Settings(secret_key="test-only-secret-key-not-for-deployment", _env_file=None)
    errors = validate_config(db, config, incomplete)
    assert errors
    assert config.status is IntegrationConfigStatus.DRAFT
    settings = configured_settings(tmp_path, wrapper)
    assert validate_config(db, config, settings) == []
    assert config.status is IntegrationConfigStatus.VALIDATED


def test_mock_status_chain_uses_local_wrapper_parser_and_ready_gate(db, tmp_path) -> None:
    remote = Path(__file__).parent / "fixtures" / "fake_services.sh"
    wrapper = tmp_path / "ssh-wrapper.sh"
    wrapper.write_text(
        '#!/bin/sh\nexec "$OPSPILOT_REMOTE_SERVICES_SCRIPT" "$@"\n', encoding="utf-8"
    )
    wrapper.chmod(0o755)
    settings = configured_settings(tmp_path, wrapper)
    config = save_fixture_config(db)
    config.remote_services_path = str(remote.resolve())
    config.remote_working_directory = str(tmp_path.resolve())
    assert validate_config(db, config, settings) == []
    environment = db.get(Environment, ENVIRONMENT_ID)
    host = db.get(Host, HOST_ID)
    service = db.get(Service, SERVICE_ID)
    assert environment and host and service
    details, result = run_status_test(config, environment, host, service, settings)
    assert result.success
    assert details["parsed_state"] == "RUNNING"
    assert details["exit_code"] == 0
    config.last_ssh_test_ok = True
    config.last_status_test_ok = True
    config.last_test_details = {
        "ssh": {HOST_ID: {"success": True}},
        "status": {f"{HOST_ID}:{SERVICE_ID}": {"success": True}},
    }
    config.status = IntegrationConfigStatus.READY
    config.enabled = False
    assert dynamic_configuration_readiness(db, settings)["status"] == "not_ready"
    config.enabled = True
    assert dynamic_configuration_readiness(db, settings)["status"] == "ready"
    (tmp_path / "ops-key-01").chmod(0o644)
    assert dynamic_configuration_readiness(db, settings)["status"] == "not_ready"


def test_ssh_probe_route_is_audited_and_sanitized(client, db, monkeypatch) -> None:
    response = client.put(f"/api/v1/admin/operations-integration/{ENVIRONMENT_ID}", json=payload())
    assert response.status_code == 200
    config = db.scalar(select(OperationsIntegrationConfig))
    assert config is not None
    config.status = IntegrationConfigStatus.VALIDATED
    db.commit()

    def fake_probe(_config, _host, _settings):
        return {
            "success": True,
            "latency_ms": 12,
            "error": None,
            "exit_code": 0,
            "host_fingerprint": "SHA256:fixture",
            "host_key_status": "strict_known_hosts",
        }

    monkeypatch.setattr("app.api.routes.integration_config.test_ssh", fake_probe)
    tested = client.post(
        f"/api/v1/admin/operations-integration/{ENVIRONMENT_ID}/test-ssh/{HOST_ID}"
    )
    assert tested.status_code == 200
    assert tested.json()["data"]["success"] is True
    audit = db.scalar(select(AuditLog).where(AuditLog.event_type == "INTEGRATION_SSH_TESTED"))
    assert audit is not None
    assert "private" not in str(audit.details).lower()


def test_status_route_uses_read_only_profile_and_is_audited(client, db, monkeypatch) -> None:
    assert (
        client.put(
            f"/api/v1/admin/operations-integration/{ENVIRONMENT_ID}", json=payload()
        ).status_code
        == 200
    )
    config = db.scalar(select(OperationsIntegrationConfig))
    assert config is not None
    config.status = IntegrationConfigStatus.VALIDATED
    config.last_test_details = {"ssh": {HOST_ID: {"success": True}}, "status": {}}
    db.commit()

    def fake_status(_config, _environment, _host, _service, _settings):
        result = ExecutionResult(
            status=TargetStatus.SUCCEEDED,
            output="running",
            error_message=None,
            duration_ms=7,
            exit_code=0,
            dry_run=False,
            service_state="RUNNING",
        )
        return {
            "success": True,
            "result": "SUCCESS",
            "command_profile": {"action": "status", "argv": ["status"]},
            "duration_ms": 7,
            "exit_code": 0,
            "parsed_state": "RUNNING",
            "stdout": "running",
            "stderr": "",
        }, result

    monkeypatch.setattr("app.api.routes.integration_config.test_status", fake_status)
    tested = client.post(
        f"/api/v1/admin/operations-integration/{ENVIRONMENT_ID}/test-status/{HOST_ID}/{SERVICE_ID}"
    )
    assert tested.status_code == 200
    assert tested.json()["data"]["command_profile"]["action"] == "status"
    db.expire_all()
    config = db.scalar(select(OperationsIntegrationConfig))
    assert config is not None and config.status is IntegrationConfigStatus.READY
    audit = db.scalar(select(AuditLog).where(AuditLog.event_type == "INTEGRATION_STATUS_TESTED"))
    assert audit is not None


def test_all_targets_must_pass_before_ready(db) -> None:
    body = payload()
    body["hosts"].append(
        {
            "id": "10000000-0000-0000-0000-000000000002",
            "name": "mock-host-fail",
            "address": "127.0.0.2",
            "ssh_port": 22,
            "ssh_username": "opspilot",
            "credential_reference": "ops-key-01",
        }
    )
    body["services"][0]["host_names"].append("mock-host-fail")
    body["allowlist"]["hosts"].append("mock-host-fail")
    environment = db.get(Environment, ENVIRONMENT_ID)
    assert environment is not None
    config = save_config(db, environment, IntegrationConfigInput.model_validate(body))
    config.last_test_details = {
        "ssh": {HOST_ID: {"success": True}},
        "status": {f"{HOST_ID}:{SERVICE_ID}": {"success": True}},
    }
    assert all_configured_tests_passed(db, config) == (False, False)
    second_host_id = "10000000-0000-0000-0000-000000000002"
    config.last_test_details["ssh"][second_host_id] = {"success": True}
    assert all_configured_tests_passed(db, config) == (True, False)
    config.last_test_details["status"][f"{second_host_id}:{SERVICE_ID}"] = {"success": True}
    assert all_configured_tests_passed(db, config) == (True, True)


def test_local_services_can_bootstrap_without_yaml_runtime_targets(tmp_path) -> None:
    wrapper = tmp_path / "ssh-wrapper.sh"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    settings = Settings(
        secret_key="test-only-secret-key-not-for-deployment",
        environment_mode="integration-test",
        executor_type="local_services",
        dry_run_only=False,
        execution_acknowledged=True,
        production_operations_enabled=False,
        write_operations_enabled=True,
        services_script_path=str(wrapper),
        services_working_directory=str(tmp_path),
        services_command_profile="pending-confirmation",
        allowed_environments="",
        allowed_hosts="",
        allowed_services="",
        allowed_actions="status",
        _env_file=None,
    )
    assert settings.allowed_environment_set == frozenset()
    assert settings.services_command_profile == "pending-confirmation"


def test_yaml_only_deployment_has_no_dynamic_ready_overlay(db) -> None:
    settings = SimpleNamespace()
    assert dynamic_configuration_readiness(db, settings) is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda body: body["allowlist"].update(actions=["status", "start"]),
        lambda body: body["execution"].update(status_argv=["start", "{service}"]),
        lambda body: body["execution"].update(status_argv=["status", "{shell}"]),
        lambda body: body["hosts"][0].update(ssh_username="opspilot;id"),
        lambda body: body["parser"]["stdout_regex"].update(running="(a+)+$"),
    ],
)
def test_security_validation_rejects_write_shell_and_username_injection(mutation) -> None:
    body = payload()
    mutation(body)
    with pytest.raises(ValueError):
        IntegrationConfigInput.model_validate(body)


@pytest.mark.parametrize(
    "field,argv",
    [
        ("status_argv", ["ansible-playbook", "status.yml"]),
        ("status_argv", ["status", "status.yml"]),
        ("start_argv", ["start", "start.yml", "{service}"]),
        ("stop_argv", ["stop", "ansible-playbook", "{service}"]),
        ("start_argv", ["start"]),
        ("stop_argv", ["stop", ""]),
    ],
)
def test_execution_argv_accepts_only_services_sh_contract(field: str, argv: list[str]) -> None:
    body = payload()
    body["allowlist"]["actions"] = ["status", field.removesuffix("_argv")]
    body["execution"][field] = argv
    with pytest.raises(ValueError):
        IntegrationConfigInput.model_validate(body)


def test_dynamic_start_stop_profile_executes_and_verifies_state(db, tmp_path) -> None:
    remote = Path(__file__).parent / "fixtures" / "fake_services.sh"
    wrapper = tmp_path / "ssh-wrapper.sh"
    wrapper.write_text(
        '#!/bin/sh\nexec "$OPSPILOT_REMOTE_SERVICES_SCRIPT" "$@"\n', encoding="utf-8"
    )
    wrapper.chmod(0o755)
    settings = configured_settings(tmp_path, wrapper)
    settings.write_operations_enabled = True
    settings.allowed_actions = "status"
    body = payload()
    body["allowlist"]["actions"] = ["status", "start", "stop"]
    body["execution"]["start_argv"] = ["start", "{environment}", "{host}", "{service}"]
    body["execution"]["stop_argv"] = ["stop", "{environment}", "{host}", "{service}"]
    environment = db.get(Environment, ENVIRONMENT_ID)
    host = db.get(Host, HOST_ID)
    assert environment and host
    config = save_config(db, environment, IntegrationConfigInput.model_validate(body))
    config.remote_services_path = str(remote.resolve())
    config.remote_working_directory = str(tmp_path.resolve())
    assert validate_config(db, config, settings) == []
    executor = build_config_executor(config, host, settings)
    target = ExecutionTarget(environment="test-mock", host="mock-host-ok", service="mock-service")
    context = {"task_id": "dynamic-e2e", "parameters": {}, "timeout_seconds": 10}

    stopped = executor.execute(OperationAction.STOP, target, context)
    assert stopped.success and stopped.service_state == "STOPPED"
    assert executor.execute(OperationAction.STATUS, target, context).service_state == "STOPPED"
    started = executor.execute(OperationAction.START, target, context)
    assert started.success and started.service_state == "RUNNING"
    assert executor.execute(OperationAction.STATUS, target, context).service_state == "RUNNING"


def test_dynamic_write_validation_fails_closed_on_platform_and_profile(db, tmp_path) -> None:
    wrapper = tmp_path / "ssh-wrapper.sh"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    body = payload()
    body["allowlist"]["actions"] = ["status", "start"]
    body["execution"]["start_argv"] = ["start", "{service}"]
    environment = db.get(Environment, ENVIRONMENT_ID)
    assert environment
    config = save_config(db, environment, IntegrationConfigInput.model_validate(body))
    closed = configured_settings(tmp_path, wrapper)
    errors = validate_config(db, config, closed)
    assert any("write_operations_enabled=true" in error for error in errors)

    body["execution"]["start_argv"] = []
    with pytest.raises(ValueError, match="explicit start_argv"):
        IntegrationConfigInput.model_validate(body)
