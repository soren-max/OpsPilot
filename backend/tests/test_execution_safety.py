import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.enums import OperationAction, TargetStatus
from app.executors.base import ExecutionRequest
from app.executors.factory import build_executor
from app.executors.local_script import LocalScriptExecutor, LocalScriptExecutorConfig
from app.executors.lodershell import LoderShellExecutor
from app.executors.ssh_script import SshScriptExecutor, SshScriptExecutorConfig
from app.executors.transports import FakeTransport, TransportResult
from app.parsers import LegacyServicesOutputParser, StructuredJsonParser


def request(behavior: str = "success") -> ExecutionRequest:
    return ExecutionRequest(
        action=OperationAction.STATUS,
        environment_code="demo",
        service_name="redacted-service",
        host_name="redacted-host",
        mock_behavior=behavior,
    )


def test_default_mock_writes_are_simulated_and_real_parameters_are_unset() -> None:
    settings = Settings()
    assert not settings.write_operations_enabled
    assert settings.allowed_action_set == {"status"}
    assert settings.approval_required_for_write
    assert not settings.production_operations_enabled
    assert settings.dry_run_only
    assert settings.ssh_host is None
    assert settings.ssh_user is None
    assert settings.services_script_path is None
    assert settings.ansible_inventory_path is None
    assert settings.ansible_playbook_path is None


def test_non_dry_run_mock_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Mock mode requires"):
        Settings(dry_run_only=False)


def test_executor_factory_defaults_to_mock_fixtures() -> None:
    result = build_executor(Settings()).execute(request())
    assert result.status is TargetStatus.SUCCEEDED
    assert result.output is not None
    assert "redacted-success" in result.output
    assert "redacted-host" not in result.output


@pytest.mark.parametrize("executor_name", ["local_script", "ssh_script"])
def test_named_non_mock_executors_still_use_dry_run_fixtures(executor_name: str) -> None:
    result = build_executor(Settings(executor=executor_name)).execute(request("failure"))
    assert result.status is TargetStatus.FAILED
    assert "SIMULATED" in (result.error_message or result.output or "").upper()


def test_local_script_requires_approved_path_and_ssh_rejects_non_dry_run() -> None:
    with pytest.raises(ValueError, match="use LocalServicesExecutor"):
        LocalScriptExecutor(LocalScriptExecutorConfig(None, None, dry_run_only=False))
    with pytest.raises(ValueError, match="dry-run"):
        SshScriptExecutor(SshScriptExecutorConfig(dry_run_only=False))


def test_lodershell_extension_is_read_only_and_fail_closed() -> None:
    executor = LoderShellExecutor()
    unavailable = executor.execute(request())
    assert unavailable.status is TargetStatus.FAILED
    assert unavailable.executor_type == "lodershell"

    start_request = ExecutionRequest(
        action=OperationAction.START,
        environment_code="demo",
        service_name="redacted-service",
        host_name="redacted-host",
    )
    denied = executor.execute(start_request)
    assert denied.status is TargetStatus.FAILED
    assert "only permits status" in denied.stderr


def test_structured_and_legacy_parsers_only_parse_fixture_protocols() -> None:
    fake = FakeTransport()
    structured = StructuredJsonParser().parse(request(), fake.run(request()))
    assert structured.status is TargetStatus.SUCCEEDED
    legacy_response = TransportResult(
        stdout="RESULT=FAILED;MESSAGE=SIMULATED_LEGACY_FAILURE",
        stderr="SIMULATED_STDERR",
        exit_code=2,
        duration_ms=1,
        fixture_name="redacted-legacy",
    )
    legacy = LegacyServicesOutputParser().parse(request("failure"), legacy_response)
    assert legacy.status is TargetStatus.FAILED
    assert legacy.error_message == "SIMULATED_STDERR"
