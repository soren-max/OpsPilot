import re

from app.core.enums import TargetStatus
from app.executors.base import ExecutionRequest, ExecutionResult
from app.executors.transports import TransportResult

SERVICE_STATE = re.compile(r'\\?"state\\?"\s*:\s*\\?"(running|stopped)\\?"', re.IGNORECASE)


class AnsibleOutputParser:
    """Normalize ansible-playbook process output without exposing its format to the worker."""

    def parse(self, request: ExecutionRequest, response: TransportResult) -> ExecutionResult:
        state_match = SERVICE_STATE.search(response.stdout)
        return ExecutionResult(
            status=(TargetStatus.SUCCEEDED if response.exit_code == 0 else TargetStatus.FAILED),
            output=response.stdout,
            error_message=response.stderr or None,
            duration_ms=response.duration_ms,
            exit_code=response.exit_code,
            dry_run=False,
            service_state=state_match.group(1).upper() if state_match else None,
        )
