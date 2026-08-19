from dataclasses import dataclass

from app.core.enums import OperationAction
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.executors.transports import FakeTransport
from app.parsers import OutputParser, StructuredJsonParser


@dataclass(frozen=True)
class AnsibleExecutorConfig:
    inventory_path: str | None = None
    playbook_directory: str | None = None
    working_directory: str | None = None
    binary_path: str | None = None
    services_script_path: str | None = None
    runtime_directory: str | None = None
    timeout_seconds: int = 30
    dry_run_only: bool = True
    allowed_environments: frozenset[str] = frozenset()
    allowed_hosts: frozenset[str] = frozenset()
    allowed_services: frozenset[str] = frozenset()
    allowed_actions: frozenset[str] = frozenset()


class AnsibleExecutor(BaseExecutor):
    """Legacy fixture adapter; direct ansible-playbook execution is hard disabled."""

    executor_type = "ansible"
    supported_actions = frozenset({OperationAction.STATUS})

    def __init__(
        self,
        config: AnsibleExecutorConfig,
        transport: FakeTransport | None = None,
        parser: OutputParser | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or FakeTransport()
        self.parser = parser or StructuredJsonParser()
        if not config.dry_run_only:
            raise ValueError(
                "Direct AnsibleExecutor execution is disabled; use LocalServicesExecutor"
            )

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.action is not OperationAction.STATUS:
            raise ValueError("Legacy AnsibleExecutor fixture only permits status")
        return self.parser.parse(request, self.transport.run(request))

    def build_command(self, _request: ExecutionRequest) -> list[str]:
        raise NotImplementedError("Direct ansible-playbook command construction is disabled")
