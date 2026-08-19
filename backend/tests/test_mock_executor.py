import pytest

from app.core.enums import OperationAction, TargetStatus
from app.executors.base import ExecutionRequest
from app.executors.mock import MockExecutor


@pytest.mark.parametrize(
    ("behavior", "expected"),
    [
        ("success", TargetStatus.SUCCEEDED),
        ("failure", TargetStatus.FAILED),
        ("timeout", TargetStatus.TIMED_OUT),
    ],
)
def test_mock_executor_scenarios(behavior: str, expected: TargetStatus) -> None:
    result = MockExecutor().execute(
        ExecutionRequest(OperationAction.STATUS, "test-mock", "mock-service", "mock-host", behavior)
    )
    assert result.status is expected


@pytest.mark.parametrize(
    ("action", "expected_state", "expected_message"),
    [
        (OperationAction.START, "RUNNING", "SIMULATED_START_OK"),
        (OperationAction.STOP, "STOPPED", "SIMULATED_STOP_OK"),
    ],
)
def test_mock_executor_simulates_writes(
    action: OperationAction, expected_state: str, expected_message: str
) -> None:
    result = MockExecutor().execute(
        ExecutionRequest(action, "test-mock", "mock-service", "mock-host")
    )
    assert result.status is TargetStatus.SUCCEEDED
    assert result.service_state == expected_state
    assert expected_message in (result.output or "")
    assert result.execution_mode == "mock"
    assert result.as_dict()["execution_mode"] == "mock"


def test_mock_stop_can_time_out() -> None:
    result = MockExecutor().execute(
        ExecutionRequest(
            OperationAction.STOP,
            "test-mock",
            "mock-service",
            "mock-host",
            "timeout",
        )
    )
    assert result.status is TargetStatus.TIMED_OUT
    assert result.exit_code == 124
