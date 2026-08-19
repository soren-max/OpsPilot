from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import OperationAction
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.executors.transports import FakeTransport
from app.parsers import OutputParser, StructuredJsonParser


@dataclass(frozen=True)
class LocalScriptExecutorConfig:
    adapter_path: str | None
    services_script_path: str | None
    start_script_path: str | None = None
    stop_script_path: str | None = None
    dry_run_only: bool = True
    timeout_seconds: int = 30
    allowed_environments: frozenset[str] = frozenset()
    allowed_hosts: frozenset[str] = frozenset()
    allowed_services: frozenset[str] = frozenset()
    allowed_actions: frozenset[str] = frozenset()


class ScriptExecutor(BaseExecutor):
    """Legacy fixture-only adapter retained for import compatibility."""

    executor_type = "local_script"

    def __init__(
        self,
        config: LocalScriptExecutorConfig,
        transport: FakeTransport | None = None,
        parser: OutputParser | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or FakeTransport()
        self.parser = parser or StructuredJsonParser()
        if not config.dry_run_only:
            self._validate_real_config()

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        if self.config.dry_run_only:
            return self.parser.parse(request, self.transport.run(request))
        raise RuntimeError(
            "Legacy ScriptExecutor real execution is disabled; use LocalServicesExecutor"
        )

    def build_command(self, request: ExecutionRequest) -> list[str]:
        del request
        raise NotImplementedError(
            "Legacy ScriptExecutor command construction is disabled; "
            "use LocalServicesExecutor and a confirmed command profile"
        )

    def resolve_script_path(self, action: OperationAction) -> str:
        """Route actions to configured wrapper scripts; never route to playbooks."""
        routes = {
            OperationAction.STATUS: self.config.services_script_path or self.config.adapter_path,
            OperationAction.START: self.config.start_script_path,
            OperationAction.STOP: self.config.stop_script_path,
        }
        if action not in routes:
            raise ValueError(f"ScriptExecutor has no script route for action: {action.value}")
        script_path = routes[action]
        if not script_path:
            raise ValueError(f"ScriptExecutor script path is not configured for: {action.value}")
        return script_path

    @staticmethod
    def build_script_arguments(request: ExecutionRequest) -> list[str]:
        del request
        raise NotImplementedError("Legacy services argument construction is disabled")

    def _validate_real_config(self) -> None:
        raise ValueError(
            "Legacy ScriptExecutor real execution is disabled; use LocalServicesExecutor"
        )

    def _validate_request(self, request: ExecutionRequest) -> None:
        if request.action is not OperationAction.STATUS:
            raise ValueError("ScriptExecutor only permits status")
        checks = {
            "environment": request.environment_code in self.config.allowed_environments,
            "host": request.host_name in self.config.allowed_hosts,
            "service": request.service_name in self.config.allowed_services,
            "action": request.action.value in self.config.allowed_actions,
        }
        rejected = [name for name, allowed in checks.items() if not allowed]
        if rejected:
            raise ValueError(
                "Execution request is outside ScriptExecutor allowlists: " + ", ".join(rejected)
            )


# Compatibility for existing imports and the legacy "local_script" executor type.
LocalScriptExecutor = ScriptExecutor
