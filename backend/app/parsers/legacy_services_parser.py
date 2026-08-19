from app.core.enums import TargetStatus
from app.executors.base import ExecutionRequest, ExecutionResult
from app.executors.transports import TransportResult


class LegacyServicesOutputParser:
    """Convert the legacy semicolon-delimited services fixture into the common result."""

    def parse(self, request: ExecutionRequest, response: TransportResult) -> ExecutionResult:
        fields = dict(item.split("=", 1) for item in response.stdout.split(";") if "=" in item)
        try:
            status = TargetStatus(fields["RESULT"])
        except (KeyError, ValueError):
            return ExecutionResult(
                status=TargetStatus.FAILED,
                output=None,
                error_message=response.stderr or "Legacy services output could not be parsed",
                duration_ms=response.duration_ms,
                exit_code=response.exit_code,
            )
        state = fields.get("STATE", "").lower()
        retryable = response.fixture_name == "redacted-retryable"
        return ExecutionResult(
            status=status,
            output=f"{fields.get('MESSAGE', 'SIMULATED_OUTPUT')} ({response.fixture_name})",
            error_message=response.stderr or None,
            duration_ms=response.duration_ms,
            exit_code=response.exit_code,
            service_state=state.upper() if state in {"running", "stopped"} else None,
            error_code="EXECUTOR_TEMPORARY_FAILURE" if retryable else None,
            retryable=retryable,
        )
