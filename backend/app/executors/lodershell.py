from collections.abc import Mapping
from typing import Any, Protocol

from app.core.enums import OperationAction, TargetStatus
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult


class LoderShellConnector(Protocol):
    """Site plugin boundary; implementations must call a reviewed API, not arbitrary shell."""

    def status(
        self,
        *,
        environment: str,
        service: str,
        host: str,
        params: Mapping[str, Any],
        timeout_seconds: int,
    ) -> ExecutionResult: ...


class LoderShellExecutor(BaseExecutor):
    """Read-only extension point for a future site-approved LoderShell connector."""

    executor_type = "lodershell"

    def __init__(self, connector: LoderShellConnector | None = None) -> None:
        self.connector = connector

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.action is not OperationAction.STATUS:
            return ExecutionResult(
                status=TargetStatus.FAILED,
                output=None,
                error_message="LoderShellExecutor only permits status",
                duration_ms=0,
                exit_code=126,
            )
        if self.connector is None:
            return ExecutionResult(
                status=TargetStatus.FAILED,
                output=None,
                error_message="LoderShell connector is not configured",
                duration_ms=0,
                exit_code=126,
            )
        return self.connector.status(
            environment=request.environment_code,
            service=request.service_name,
            host=request.host_name,
            params=request.parameters,
            timeout_seconds=request.timeout_seconds,
        )
