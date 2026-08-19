from pathlib import Path

import pytest

from app.core.enums import OperationAction, TargetStatus
from app.executors.base import ExecutionRequest
from app.executors.local_services import (
    LocalServicesExecutor,
    LocalServicesExecutorConfig,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SCRIPT = FIXTURE_DIR / "fake_services.sh"


def executor(parser: str = "json_status", timeout: int = 2) -> LocalServicesExecutor:
    return LocalServicesExecutor(
        LocalServicesExecutorConfig(
            script_path=str(SCRIPT),
            working_directory=str(FIXTURE_DIR),
            command_profile="test-fixture-v1",
            output_parser=parser,
            timeout_seconds=timeout,
            allowed_environments=frozenset({"devtest"}),
            allowed_hosts=frozenset({"test-host"}),
            allowed_services=frozenset(
                {
                    "running",
                    "stopped",
                    "unreachable",
                    "not-found",
                    "non-zero",
                    "warning",
                    "timeout",
                    "unknown",
                }
            ),
            allowed_actions=frozenset({"status"}),
        )
    )


def request(
    service: str = "running",
    *,
    action: OperationAction = OperationAction.STATUS,
    host: str = "test-host",
    parameters: dict[str, object] | None = None,
) -> ExecutionRequest:
    return ExecutionRequest(
        action=action,
        environment_code="devtest",
        service_name=service,
        host_name=host,
        timeout_seconds=1,
        parameters=parameters or {},
    )


def test_running_executes_fake_script_and_preserves_contract() -> None:
    result = executor().execute(request())
    assert result.status is TargetStatus.SUCCEEDED
    assert result.service_state == "RUNNING"
    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.executor_type == "local_services"
    assert result.target_summary == "devtest/test-host/running"
    assert set(result.as_dict()) == {
        "success",
        "stdout",
        "stderr",
        "exit_code",
        "duration_ms",
        "executor_type",
        "target_summary",
        "error_code",
        "timed_out",
        "execution_mode",
        "retryable",
    }


def test_executor_uses_argv_shell_false_and_configured_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 1234
        returncode = 0

        def communicate(self, timeout: int) -> tuple[str, str]:
            captured["timeout"] = timeout
            return '{"state":"running"}', ""

    def fake_popen(argv: list[str], **kwargs: object) -> FakeProcess:
        captured["argv"] = argv
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = executor().execute(request())
    assert result.success
    assert captured["argv"] == [
        str(SCRIPT),
        "status",
        "devtest",
        "test-host",
        "running",
    ]
    assert captured["shell"] is False
    assert captured["cwd"] == str(FIXTURE_DIR)
    assert captured["start_new_session"] is True


@pytest.mark.parametrize(
    ("service", "expected_status", "exit_code"),
    [
        ("stopped", TargetStatus.SUCCEEDED, 0),
        ("unreachable", TargetStatus.UNREACHABLE, 4),
        ("not-found", TargetStatus.FAILED, 5),
        ("non-zero", TargetStatus.FAILED, 7),
    ],
)
def test_exit_codes_and_states(service: str, expected_status: TargetStatus, exit_code: int) -> None:
    result = executor().execute(request(service))
    assert result.status is expected_status
    assert result.exit_code == exit_code


def test_stderr_warning_with_zero_exit_does_not_force_failure() -> None:
    result = executor().execute(request("warning"))
    assert result.status is TargetStatus.SUCCEEDED
    assert result.stderr == "redacted warning\n"


def test_stdout_stderr_and_nonzero_exit_are_preserved_together() -> None:
    result = executor().execute(request("non-zero"))
    assert result.stdout == "partial stdout\n"
    assert result.stderr == "ansible failed\n"
    assert result.exit_code == 7


def test_unparseable_stdout_never_becomes_running() -> None:
    result = executor().execute(request("unknown"))
    assert result.status is TargetStatus.FAILED
    assert result.service_state == "PARSE_FAILED"
    assert result.error_code == "OUTPUT_PARSE_FAILED"


def test_timeout_terminates_fake_process() -> None:
    result = executor(timeout=1).execute(request("timeout"))
    assert result.status is TargetStatus.TIMED_OUT
    assert result.exit_code == 124
    assert result.timed_out
    assert result.error_code == "EXECUTION_TIMEOUT"


def test_pending_profile_never_launches_process(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def forbidden(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("subprocess.Popen", forbidden)
    configured = executor()
    pending = LocalServicesExecutor(
        LocalServicesExecutorConfig(
            **{
                **configured.config.__dict__,
                "command_profile": "pending-confirmation",
            }
        )
    )
    result = pending.execute(request())
    assert result.error_code == "COMMAND_PROFILE_NOT_CONFIGURED"
    assert not called


def test_non_executable_script_is_rejected_before_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = tmp_path / "fake_services.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script.chmod(0o644)
    called = False

    def forbidden(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("subprocess.Popen", forbidden)
    configured = executor()
    invalid = LocalServicesExecutor(
        LocalServicesExecutorConfig(
            **{
                **configured.config.__dict__,
                "script_path": str(script),
                "working_directory": str(tmp_path),
            }
        )
    )
    result = invalid.execute(request())
    assert result.error_code == "EXECUTION_REQUEST_REJECTED"
    assert "not executable" in result.stderr
    assert not called


@pytest.mark.parametrize(
    "bad_request",
    [
        request(action=OperationAction.START),
        request(host="host;id"),
        request(parameters={"command": "id"}),
        request(parameters={"playbook": "start.yml"}),
        request(parameters={"extra_vars": {"x": "y"}}),
    ],
)
def test_write_injection_and_arbitrary_command_fields_are_rejected(
    bad_request: ExecutionRequest,
) -> None:
    result = executor().execute(bad_request)
    assert result.status is TargetStatus.FAILED
    assert result.error_code == "EXECUTION_REQUEST_REJECTED"
