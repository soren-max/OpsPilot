from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from app.core.command_profiles import CommandAction, CommandProfile, OutputParserConfig
from app.core.enums import OperationAction, TargetStatus
from app.executors.base import ExecutionRequest
from app.executors.local_services import LocalServicesExecutor, LocalServicesExecutorConfig

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures"
FIXTURE_SCRIPT = FIXTURE_DIRECTORY / "fake_services.sh"
PROFILE = CommandProfile(
    capabilities=["status", "start", "stop"],
    parser="fixture-json",
    actions={
        action: CommandAction(argv=[action, "{environment}", "{host}", "{service}"])
        for action in ("status", "start", "stop")
    },
)


@pytest.fixture(autouse=True)
def cleanup_fixture_state():
    state_directory = FIXTURE_DIRECTORY / ".fake-services-state"
    yield
    if state_directory.is_dir():
        for item in state_directory.iterdir():
            item.unlink()
        state_directory.rmdir()


def fixture_executor(
    *, timeout: int = 2, max_output: int = 4096, services: set[str] | None = None
) -> LocalServicesExecutor:
    return LocalServicesExecutor(
        LocalServicesExecutorConfig(
            script_path=str(FIXTURE_SCRIPT.resolve()),
            working_directory=str(FIXTURE_DIRECTORY.resolve()),
            command_profile="test-fixture-v2",
            command_profiles={"test-fixture-v2": PROFILE},
            output_parsers={"fixture-json": OutputParserConfig(type="json")},
            timeout_seconds=timeout,
            max_output_bytes=max_output,
            termination_grace_seconds=0.2,
            allowed_environments=frozenset({"fixture"}),
            allowed_hosts=frozenset({"fixture-host"}),
            allowed_services=frozenset(
                services
                or {
                    "stateful",
                    "timeout",
                    "ignore-term",
                    "large-output",
                    "invalid-encoding",
                }
            ),
            allowed_actions=frozenset({"status", "start", "stop"}),
        )
    )


def request(
    action: OperationAction, service: str, task_id: str = "fixture-task"
) -> ExecutionRequest:
    return ExecutionRequest(
        action=action,
        environment_code="fixture",
        host_name="fixture-host",
        service_name=service,
        task_id=task_id,
        timeout_seconds=2,
    )


def test_real_start_stop_and_write_verification_state() -> None:
    executor = fixture_executor(services={"stateful"})
    assert executor.execute(request(OperationAction.STOP, "stateful")).success
    stopped = executor.execute(request(OperationAction.STATUS, "stateful"))
    assert stopped.success and stopped.service_state == "STOPPED"
    assert executor.execute(request(OperationAction.START, "stateful")).success
    running = executor.execute(request(OperationAction.STATUS, "stateful"))
    assert running.success and running.service_state == "RUNNING"


@pytest.mark.parametrize("action", [OperationAction.START, OperationAction.STOP])
def test_status_only_executor_rejects_write_even_when_profile_declares_it(
    action: OperationAction,
) -> None:
    configured = fixture_executor(services={"stateful"})
    status_only = LocalServicesExecutor(
        LocalServicesExecutorConfig(
            **{
                **configured.config.__dict__,
                "allowed_actions": frozenset({"status"}),
            }
        )
    )
    result = status_only.execute(request(action, "stateful"))
    assert result.status is TargetStatus.FAILED
    assert result.error_code == "EXECUTION_REQUEST_REJECTED"
    assert "action" in result.stderr


def test_timeout_output_truncation_and_invalid_encoding() -> None:
    timeout = fixture_executor(timeout=1).execute(request(OperationAction.STATUS, "timeout"))
    assert timeout.status is TargetStatus.TIMED_OUT and timeout.error_code == "EXECUTION_TIMEOUT"
    large = fixture_executor(max_output=1024).execute(
        request(OperationAction.STATUS, "large-output")
    )
    assert len(large.stdout.encode()) <= 1024
    assert "[output truncated]" in large.stdout
    invalid = fixture_executor().execute(request(OperationAction.STATUS, "invalid-encoding"))
    assert "�" in invalid.stdout


def test_running_cancel_escalates_and_leaves_no_fixture_process() -> None:
    executor = fixture_executor(timeout=10)
    result: list[object] = []
    thread = threading.Thread(
        target=lambda: result.append(
            executor.execute(request(OperationAction.STATUS, "ignore-term", "cancel-me"))
        )
    )
    thread.start()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not executor.cancel("cancel-me"):
        time.sleep(0.02)
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert result and result[0].status is TargetStatus.CANCELLED  # type: ignore[union-attr]


def test_fixture_profile_cannot_bind_another_executable(tmp_path: Path) -> None:
    script = tmp_path / "fake_services.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    configured = fixture_executor()
    rejected = LocalServicesExecutor(
        LocalServicesExecutorConfig(
            **{
                **configured.config.__dict__,
                "script_path": str(script),
                "working_directory": str(tmp_path),
            }
        )
    ).execute(request(OperationAction.STATUS, "stateful"))
    assert rejected.error_code == "EXECUTION_REQUEST_REJECTED"
    assert "repository fake_services.sh" in rejected.stderr
