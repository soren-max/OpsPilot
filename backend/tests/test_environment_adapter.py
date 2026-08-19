from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.adapters import ServicesAdapter, ServicesAdapterConfig
from app.core.config import Settings
from app.core.enums import OperationAction, TargetStatus
from app.core.environment_config import load_environment_config
from app.executors.ansible_playbook import AnsiblePlaybookExecutor
from app.executors.base import ExecutionRequest, ExecutionResult
from app.executors.dry_run import DryRunExecutor
from app.executors.factory import ExecutorFactory
from app.executors.mock import MockExecutor
from app.executors.transports import TransportResult
from app.parsers import LegacyServicesOutputParser, StructuredJsonParser

CONFIG_ROOT = Path(__file__).parents[2] / "config" / "environments"


def test_mock_yaml_loads_and_settings_overlay_defaults() -> None:
    profile = load_environment_config(CONFIG_ROOT / "mock.yaml", {})
    assert profile.normalized_mode == "mock"
    assert profile.executor.type == "mock"
    settings = Settings(environment_config_path=str(CONFIG_ROOT / "mock.yaml"), _env_file=None)
    assert settings.environment_mode == "mock"
    assert settings.selected_executor == "mock"
    assert settings.dry_run_only is True
    assert settings.write_operations_enabled is False
    assert settings.allowed_action_set == {"status"}
    assert settings.approval_required_for_write is True


def test_test_yaml_loads_as_safe_ansible_protocol_adapter() -> None:
    profile = load_environment_config(CONFIG_ROOT / "test.yaml", {})
    assert profile.normalized_mode == "integration-test"
    assert profile.executor.type == "ansible"
    assert profile.security.dry_run_only is True
    settings = Settings(
        environment_config_path=str(CONFIG_ROOT / "test.yaml"),
        write_operations_enabled=False,
        allowed_actions="status",
        approval_required_for_write=True,
        _env_file=None,
    )
    assert isinstance(ExecutorFactory(settings).create(), AnsiblePlaybookExecutor)
    assert settings.real_integration_execution_enabled is False


@pytest.mark.parametrize(
    "override",
    [
        "OPSPILOT_CONFIG__EXECUTOR__TYPE",
        "OPSPILOT_CONFIG__EXECUTOR__TIMEOUT",
        "OPSPILOT_CONFIG__SECURITY__WRITE_ENABLED",
        "OPSPILOT_CONFIG__APPROVAL__ALLOW_SELF_APPROVAL",
        "OPSPILOT_CONFIG__ALLOWLIST__HOSTS",
        "OPSPILOT_CONFIG__SERVICES__SCRIPT_PATH",
        "OPSPILOT_CONFIG__SERVICES__OUTPUT_PARSER",
        "OPSPILOT_CONFIG__COMMAND_PROFILES__SITE__CAPABILITIES",
        "OPSPILOT_CONFIG__OUTPUT_PARSERS__SITE__TYPE",
    ],
)
def test_security_critical_nested_environment_overrides_are_rejected(
    override: str,
) -> None:
    with pytest.raises(ValueError, match="Nested configuration environment overrides"):
        load_environment_config(CONFIG_ROOT / "test.yaml", {override: "unsafe"})


def test_direct_typed_settings_override_remains_supported() -> None:
    settings = Settings(
        environment_config_path=str(CONFIG_ROOT / "test.yaml"),
        executor_type="mock",
    )
    assert settings.selected_executor == "mock"


def test_nested_override_channel_is_rejected_without_yaml_config(monkeypatch) -> None:
    monkeypatch.setenv("OPSPILOT_CONFIG__SECURITY__WRITE_ENABLED", "true")
    with pytest.raises(ValueError, match="Nested configuration environment overrides"):
        Settings(_env_file=None)


def test_remote_configuration_is_mapped_without_site_defaults(tmp_path: Path) -> None:
    profile = tmp_path / "ssh-dry-run.yaml"
    profile.write_text(
        """
environment:
  name: test
  mode: integration-test
executor:
  type: ssh_script
ssh:
  enabled: true
  port: 2222
  timeout: 12
remote:
  working_directory: /configured/remotely
services:
  script_path: /configured/status-entrypoint
security:
  dry_run_only: true
allowlist:
  actions: [status]
""",
        encoding="utf-8",
    )
    settings = Settings(environment_config_path=str(profile), _env_file=None)
    assert settings.selected_executor == "ssh_script"
    assert settings.ssh_port == 2222
    assert settings.ssh_connect_timeout_seconds == 12
    assert settings.remote_working_directory == "/configured/remotely"
    assert settings.services_script_path == "/configured/status-entrypoint"


def test_ssh_private_key_path_must_be_injected(tmp_path: Path) -> None:
    profile = tmp_path / "ssh-key.yaml"
    profile.write_text(
        """
environment:
  name: test
  mode: integration-test
executor:
  type: ssh_script
ssh:
  host: ${TEST_SSH_HOST}
  username: ${TEST_SSH_USER}
  private_key: ${TEST_SSH_KEY_PATH}
security:
  dry_run_only: true
""",
        encoding="utf-8",
    )
    loaded = load_environment_config(
        profile,
        {
            "TEST_SSH_HOST": "ssh.example.invalid",
            "TEST_SSH_USER": "opspilot-readonly",
            "TEST_SSH_KEY_PATH": "/injected/key-path",
        },
    )
    assert loaded.ssh.host == "ssh.example.invalid"
    assert loaded.ssh.username == "opspilot-readonly"
    assert loaded.ssh.private_key == "/injected/key-path"

    profile.write_text(profile.read_text().replace("${TEST_SSH_KEY_PATH}", "inline-secret"))
    with pytest.raises(ValueError, match="Sensitive field is forbidden"):
        load_environment_config(profile, {})


def test_missing_configuration_is_rejected_and_production_defaults_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        load_environment_config(tmp_path / "missing.yaml", {})
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text(
        "environment:\n  name: incomplete\n  mode: mock\n",
        encoding="utf-8",
    )
    with pytest.raises(PydanticValidationError, match="executor"):
        load_environment_config(incomplete, {})
    production = load_environment_config(CONFIG_ROOT / "prod.example.yaml", {})
    assert production.normalized_mode == "production"
    configured = Settings(environment_config_path=str(CONFIG_ROOT / "prod.example.yaml"))
    assert not configured.write_operations_enabled
    assert not configured.production_operations_enabled
    assert not configured.allow_self_approval
    assert configured.services_command_profile == "pending-confirmation"


@pytest.mark.parametrize("mode", ["integration", "internal-test", "development", "simulation"])
def test_ambiguous_environment_modes_fail_fast(tmp_path: Path, mode: str) -> None:
    profile = tmp_path / "invalid-mode.yaml"
    profile.write_text(
        f"environment:\n  name: test\n  mode: {mode}\nexecutor:\n  type: mock\n",
        encoding="utf-8",
    )
    with pytest.raises(PydanticValidationError, match="integration-test"):
        load_environment_config(profile, {})


@pytest.mark.parametrize("field", ["start_command_profile", "stop_command_profile"])
def test_legacy_service_command_profile_fields_are_rejected(tmp_path: Path, field: str) -> None:
    profile = tmp_path / "legacy-profile.yaml"
    profile.write_text(
        "environment:\n  name: test\n  mode: mock\nexecutor:\n  type: mock\n"
        f"services:\n  {field}: legacy\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"command_profiles\.<profile>\.actions"):
        load_environment_config(profile, {})


def test_legacy_service_command_profile_environment_setting_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="Unsupported legacy OPSPILOT settings"):
        Settings(services_start_command_profile="legacy", _env_file=None)


def test_obsolete_test_acknowledgement_setting_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="OPSPILOT_EXECUTION_ACKNOWLEDGED"):
        Settings(test_execution_acknowledged=True, _env_file=None)


def test_real_test_profile_requires_explicit_acknowledgement(tmp_path: Path) -> None:
    profile = tmp_path / "real-test.yaml"
    profile.write_text(
        """
environment:
  name: test
  mode: integration-test
executor:
  type: ansible
ansible: {}
ssh:
  enabled: false
services: {}
security:
  write_enabled: true
  production_enabled: false
  dry_run_only: false
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="OPSPILOT_EXECUTION_ACKNOWLEDGED"):
        load_environment_config(profile, {})


@pytest.mark.parametrize(
    ("executor_type", "expected_type"),
    [
        ("mock", MockExecutor),
        ("dry_run", DryRunExecutor),
        ("ansible", AnsiblePlaybookExecutor),
    ],
)
def test_factory_selects_strategy(executor_type: str, expected_type: type[object]) -> None:
    settings = Settings(
        environment_mode="integration-test" if executor_type == "ansible" else "mock",
        executor_type=executor_type,
        dry_run_only=True,
        write_operations_enabled=executor_type != "ansible",
    )
    assert isinstance(ExecutorFactory(settings).create(), expected_type)


def test_legacy_real_script_yaml_is_rejected(tmp_path: Path) -> None:
    profile = tmp_path / "script.yaml"
    profile.write_text(
        """
environment:
  name: devtest
  mode: integration-test
executor:
  type: script
  timeout: 60
  retry: 0
services:
  script_path: /home/opspilot/opspilot-ansible/bin/status.sh
security:
  write_enabled: false
  production_enabled: false
  dry_run_only: false
  execution_acknowledged: true
allowlist:
  environments: [devtest]
  hosts: [EMS04]
  services: [example-service]
  actions: [status]
""",
        encoding="utf-8",
    )
    with pytest.raises(PydanticValidationError, match="disabled for real execution"):
        Settings(environment_config_path=str(profile), _env_file=None)


def test_common_execution_contract_and_parser_strategies() -> None:
    request = ExecutionRequest(OperationAction.STATUS, "mock", "demo-service", "demo-host")
    mock_result = MockExecutor().execute(request)
    assert isinstance(mock_result, ExecutionResult)
    assert mock_result.success
    assert mock_result.stdout
    assert mock_result.stderr == ""
    assert request.hosts == ("demo-host",)

    json_result = StructuredJsonParser().parse(
        request,
        TransportResult(
            stdout='{"status":"SUCCEEDED","message":"ok","state":"running"}',
            stderr="",
            exit_code=0,
            duration_ms=5,
            fixture_name="json-fixture",
        ),
    )
    legacy_result = LegacyServicesOutputParser().parse(
        request,
        TransportResult(
            stdout="RESULT=FAILED;MESSAGE=not-running;STATE=stopped",
            stderr="fixture failure",
            exit_code=3,
            duration_ms=6,
            fixture_name="legacy-fixture",
        ),
    )
    assert json_result.service_state == "RUNNING"
    assert legacy_result.status is TargetStatus.FAILED
    assert legacy_result.exit_code == 3


def test_services_adapter_builds_argv_without_execution() -> None:
    request = ExecutionRequest(OperationAction.START, "test", "gateway", "test-host")
    adapter = ServicesAdapter(ServicesAdapterConfig("/adapter/services.sh"))
    assert adapter.build_command(request) == ["/adapter/services.sh", "start", "gateway"]
