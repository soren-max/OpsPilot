from collections.abc import Mapping
from typing import Any, Protocol

from app.core.enums import OperationAction, TargetStatus
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult


class RemoteStatusConnector(Protocol):
    """Generic read-only connector boundary for a reviewed remote status API."""

    def status(
        self,
        *,
        environment: str,
        service: str,
        host: str,
        params: Mapping[str, Any],
        timeout_seconds: int,
    ) -> ExecutionResult: ...


class RemoteStatusExecutor(BaseExecutor):
    """Read-only extension point that fails closed when no connector is configured."""

    executor_type = "remote_status"

    def __init__(self, connector: RemoteStatusConnector | None = None) -> None:
        self.connector = connector

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.action is not OperationAction.STATUS:
            return ExecutionResult(
                status=TargetStatus.FAILED,
                output=None,
                error_message="RemoteStatusExecutor only permits status",
                duration_ms=0,
                exit_code=126,
            )
        if self.connector is None:
            return ExecutionResult(
                status=TargetStatus.FAILED,
                output=None,
                error_message="Remote status connector is not configured",
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
