import pytest

from app.core.enums import OperationAction, TargetStatus
from app.executors.base import ExecutionRequest
from app.executors.local_script import LocalScriptExecutorConfig, ScriptExecutor


def request() -> ExecutionRequest:
    return ExecutionRequest(
        action=OperationAction.STATUS,
        environment_code="devtest",
        service_name="redacted-service",
        host_name="redacted-host",
    )


def test_legacy_script_executor_real_execution_is_hard_disabled() -> None:
    with pytest.raises(ValueError, match="use LocalServicesExecutor"):
        ScriptExecutor(
            LocalScriptExecutorConfig(
                adapter_path=None,
                services_script_path="/redacted/status.sh",
                dry_run_only=False,
                allowed_environments=frozenset({"devtest"}),
                allowed_hosts=frozenset({"redacted-host"}),
                allowed_services=frozenset({"redacted-service"}),
                allowed_actions=frozenset({"status"}),
            )
        )


def test_legacy_script_executor_remains_fixture_only_for_compatibility() -> None:
    executor = ScriptExecutor(
        LocalScriptExecutorConfig(
            adapter_path=None,
            services_script_path=None,
            dry_run_only=True,
        )
    )
    result = executor.execute(request())
    assert result.status is TargetStatus.SUCCEEDED
    assert result.dry_run
    with pytest.raises(NotImplementedError, match="confirmed command profile"):
        executor.build_command(request())
