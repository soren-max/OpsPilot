from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Protocol, overload

from app.core.enums import OperationAction, TargetStatus


@dataclass(frozen=True)
class ExecutionRequest:
    action: OperationAction
    environment_code: str
    service_name: str
    host_name: str
    mock_behavior: str = "success"
    timeout_seconds: int = 30
    task_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def environment(self) -> str:
        return self.environment_code

    @property
    def service(self) -> str:
        return self.service_name

    @property
    def hosts(self) -> tuple[str, ...]:
        return (self.host_name,)


@dataclass(frozen=True)
class ExecutionTarget:
    """Transport-neutral target supplied by the worker/business layer."""

    environment: str
    service: str
    host: str
    mock_behavior: str = "success"


@dataclass(frozen=True)
class ExecutionResult:
    status: TargetStatus
    output: str | None
    error_message: str | None
    duration_ms: int
    exit_code: int = 0
    dry_run: bool = True
    service_state: str | None = None
    executor_type: str = "unknown"
    target_summary: str = ""
    error_code: str | None = None
    timed_out: bool = False
    execution_mode: str = "real"
    retryable: bool = False

    @property
    def success(self) -> bool:
        return self.status is TargetStatus.SUCCEEDED

    @property
    def stdout(self) -> str:
        return self.output or ""

    @property
    def stderr(self) -> str:
        return self.error_message or ""

    @property
    def duration(self) -> float:
        return self.duration_ms / 1000

    def as_dict(self) -> dict[str, bool | str | int | None]:
        """Expose the stable transport-neutral result contract."""
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "executor_type": self.executor_type,
            "target_summary": self.target_summary,
            "error_code": self.error_code,
            "timed_out": self.timed_out,
            "execution_mode": self.execution_mode,
            "retryable": self.retryable,
        }

    @property
    def target_results(self) -> tuple[TargetExecutionResult, ...]:
        return ()


@dataclass(frozen=True)
class TargetExecutionResult:
    service_name: str
    host_name: str
    result: ExecutionResult


class Executor(Protocol):
    executor_type: str

    def execute(
        self,
        action: OperationAction | str,
        target: ExecutionTarget,
        params: Mapping[str, Any] | None = None,
    ) -> ExecutionResult: ...

    @property
    def capabilities(self) -> frozenset[OperationAction]: ...


class BaseExecutor(ABC):
    """Common executor contract; concrete executors own all transport details."""

    executor_type = "unknown"
    supported_actions: frozenset[OperationAction] = frozenset()

    @property
    def capabilities(self) -> frozenset[OperationAction]:
        return self.supported_actions

    @overload
    def execute(self, action: ExecutionRequest) -> ExecutionResult: ...

    @overload
    def execute(
        self,
        action: OperationAction | str,
        target: ExecutionTarget,
        params: Mapping[str, Any] | None = None,
    ) -> ExecutionResult: ...

    def execute(
        self,
        action: OperationAction | str | ExecutionRequest,
        target: ExecutionTarget | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> ExecutionResult:
        """Normalize the public execute(action, target, params) call.

        ExecutionRequest remains accepted temporarily for internal API compatibility.
        """
        request = (
            action
            if isinstance(action, ExecutionRequest)
            else self._build_request(action, target, params)
        )
        result = self._execute(request)
        return replace(
            result,
            executor_type=self.executor_type,
            execution_mode="mock" if self.executor_type == "mock" else "real",
        )

    @abstractmethod
    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute one normalized request."""

    @staticmethod
    def _build_request(
        action: OperationAction | str,
        target: ExecutionTarget | None,
        params: Mapping[str, Any] | None,
    ) -> ExecutionRequest:
        if target is None:
            raise TypeError("target is required")
        values = dict(params or {})
        operation = action if isinstance(action, OperationAction) else OperationAction(action)
        request_parameters = values.get("parameters", values)
        if not isinstance(request_parameters, dict):
            raise TypeError("params.parameters must be a mapping")
        return ExecutionRequest(
            action=operation,
            environment_code=target.environment,
            service_name=target.service,
            host_name=target.host,
            mock_behavior=target.mock_behavior,
            timeout_seconds=int(values.get("timeout_seconds", 30)),
            task_id=(str(values["task_id"]) if values.get("task_id") is not None else None),
            parameters=dict(request_parameters),
        )
