import json

from app.core.enums import TargetStatus
from app.executors.base import ExecutionRequest, ExecutionResult
from app.executors.transports import TransportResult


class StructuredJsonParser:
    """Convert the stable JSON services protocol into the common execution result."""

    def parse(self, request: ExecutionRequest, response: TransportResult) -> ExecutionResult:
        try:
            payload = json.loads(response.stdout)
            status = TargetStatus(str(payload["status"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return ExecutionResult(
                status=TargetStatus.FAILED,
                output=None,
                error_message=response.stderr or "Structured output could not be parsed",
                duration_ms=response.duration_ms,
                exit_code=response.exit_code,
            )
        state = payload.get("state")
        return ExecutionResult(
            status=status,
            output=f"{payload.get('message', 'SIMULATED_OUTPUT')} ({response.fixture_name})",
            error_message=response.stderr or None,
            duration_ms=response.duration_ms,
            exit_code=response.exit_code,
            service_state=str(state).upper() if state in {"running", "stopped"} else None,
        )
