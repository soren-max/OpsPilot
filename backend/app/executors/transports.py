from dataclasses import dataclass

from app.executors.base import ExecutionRequest


@dataclass(frozen=True)
class TransportResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    fixture_name: str


class FakeTransport:
    """Fixture-only transport. It never opens a network connection or starts a process."""

    def run(self, request: ExecutionRequest) -> TransportResult:
        action = request.action.value.upper()
        state = "stopped" if request.action.value == "stop" else "running"
        fixtures = {
            "success": TransportResult(
                stdout=(
                    '{"status":"SUCCEEDED","message":"SIMULATED_'
                    f'{action}_OK","state":"{state}","fixture":"redacted-success"}}'
                ),
                stderr="",
                exit_code=0,
                duration_ms=85,
                fixture_name="redacted-success",
            ),
            "failure": TransportResult(
                stdout=(
                    f"RESULT=FAILED;MESSAGE=SIMULATED_{action}_FAILURE;FIXTURE=redacted-failure"
                ),
                stderr=f"SIMULATED_STDERR: {request.action.value} operation failed",
                exit_code=2,
                duration_ms=120,
                fixture_name="redacted-failure",
            ),
            "timeout": TransportResult(
                stdout="",
                stderr="SIMULATED_STDERR: operation timed out",
                exit_code=124,
                duration_ms=30_000,
                fixture_name="redacted-timeout",
            ),
            "retryable_failure": TransportResult(
                stdout=(
                    f"RESULT=FAILED;MESSAGE=SIMULATED_{action}_TEMPORARY_FAILURE;"
                    "FIXTURE=redacted-retryable"
                ),
                stderr="SIMULATED_STDERR: temporary executor failure",
                exit_code=75,
                duration_ms=40,
                fixture_name="redacted-retryable",
            ),
        }
        return fixtures.get(request.mock_behavior, fixtures["success"])
