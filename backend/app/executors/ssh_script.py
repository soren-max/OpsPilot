from dataclasses import dataclass

from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.executors.transports import FakeTransport
from app.parsers import OutputParser, StructuredJsonParser


@dataclass(frozen=True)
class SshScriptExecutorConfig:
    adapter_path: str | None = None
    ssh_host: str | None = None
    ssh_user: str | None = None
    ssh_port: int | None = None
    ssh_jump_mode: str | None = None
    ssh_jump_host: str | None = None
    ssh_known_hosts_path: str | None = None
    ssh_private_key_path: str | None = None
    ssh_timeout_seconds: int = 10
    remote_working_directory: str | None = None
    services_script_path: str | None = None
    ansible_inventory_path: str | None = None
    ansible_playbook_path: str | None = None
    ansible_tags: str | None = None
    dry_run_only: bool = True


class SshScriptExecutor(BaseExecutor):
    """Dry-run adapter contract. It uses fixtures and never creates an SSH connection."""

    executor_type = "ssh_script"

    def __init__(
        self,
        config: SshScriptExecutorConfig,
        transport: FakeTransport | None = None,
        parser: OutputParser | None = None,
    ) -> None:
        if not config.dry_run_only:
            raise ValueError("SshScriptExecutor only supports dry-run mode")
        self.config = config
        self.transport = transport or FakeTransport()
        self.parser = parser or StructuredJsonParser()

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        return self.parser.parse(request, self.transport.run(request))


# Deployment-neutral name for future connector implementations.
RemoteExecutor = SshScriptExecutor
SSHExecutor = SshScriptExecutor
