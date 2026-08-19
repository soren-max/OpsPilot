from collections.abc import Callable, Mapping

from app.core.config import Settings
from app.core.config_types import ExecutorName
from app.executors.ansible_playbook import AnsiblePlaybookExecutor
from app.executors.base import Executor
from app.executors.dry_run import DryRunExecutor
from app.executors.local_script import LocalScriptExecutorConfig, ScriptExecutor
from app.executors.local_services import LocalServicesExecutor, LocalServicesExecutorConfig
from app.executors.mock import MockExecutor
from app.executors.ssh_script import SshScriptExecutor, SshScriptExecutorConfig

ExecutorBuilder = Callable[[Settings], Executor]


def _mock(_settings: Settings) -> Executor:
    return MockExecutor()


def _dry_run(_settings: Settings) -> Executor:
    return DryRunExecutor()


def _ansible(_settings: Settings) -> Executor:
    return AnsiblePlaybookExecutor()


def _local_services(settings: Settings) -> Executor:
    return LocalServicesExecutor(
        LocalServicesExecutorConfig(
            script_path=settings.services_script_path,
            working_directory=settings.services_working_directory,
            command_profile=settings.services_command_profile,
            output_parser=settings.services_output_parser,
            timeout_seconds=settings.execution_timeout_seconds,
            allowed_environments=settings.allowed_environment_set,
            allowed_hosts=settings.allowed_host_set,
            allowed_services=settings.allowed_service_set,
            allowed_actions=settings.allowed_action_set,
            command_profiles=settings.command_profiles,
            output_parsers=settings.output_parsers,
            process_environment=settings.services_environment,
            max_output_bytes=settings.max_output_bytes,
            termination_grace_seconds=settings.termination_grace_seconds,
        )
    )


def _local_script(settings: Settings) -> Executor:
    return ScriptExecutor(
        LocalScriptExecutorConfig(
            adapter_path=settings.script_adapter_path or settings.ops_adapter_path,
            services_script_path=settings.services_script_path,
            start_script_path=settings.services_start_script_path,
            stop_script_path=settings.services_stop_script_path,
            dry_run_only=settings.dry_run_only,
            timeout_seconds=settings.execution_timeout_seconds,
            allowed_environments=settings.allowed_environment_set,
            allowed_hosts=settings.allowed_host_set,
            allowed_services=settings.allowed_service_set,
            allowed_actions=settings.allowed_action_set,
        )
    )


def _ssh_script(settings: Settings) -> Executor:
    return SshScriptExecutor(
        SshScriptExecutorConfig(
            adapter_path=settings.ops_adapter_path,
            ssh_host=settings.ssh_host,
            ssh_user=settings.ssh_user,
            ssh_port=settings.ssh_port,
            ssh_jump_mode=settings.ssh_jump_mode,
            ssh_jump_host=settings.ssh_jump_host,
            ssh_known_hosts_path=settings.ssh_known_hosts_path,
            ssh_private_key_path=settings.ssh_private_key_path,
            ssh_timeout_seconds=settings.ssh_connect_timeout_seconds,
            remote_working_directory=settings.remote_working_directory,
            services_script_path=settings.services_script_path,
            ansible_inventory_path=settings.ansible_inventory_path,
            ansible_playbook_path=settings.ansible_playbook_path,
            ansible_tags=settings.ansible_tags,
            dry_run_only=settings.dry_run_only,
        )
    )


DEFAULT_BUILDERS: Mapping[ExecutorName, ExecutorBuilder] = {
    "mock": _mock,
    "dry_run": _dry_run,
    "script": _local_script,
    "local_script": _local_script,
    "local_services": _local_services,
    "ssh_script": _ssh_script,
    "ansible": _ansible,
    "ansible_playbook": _ansible,
}


class ExecutorFactory:
    """Select an execution strategy from validated configuration."""

    def __init__(
        self,
        settings: Settings,
        builders: Mapping[ExecutorName, ExecutorBuilder] | None = None,
    ) -> None:
        self.settings = settings
        self.builders = builders or DEFAULT_BUILDERS

    def create(self) -> Executor:
        try:
            builder = self.builders[self.settings.selected_executor]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported executor type: {self.settings.selected_executor}"
            ) from exc
        return builder(self.settings)


def build_executor(settings: Settings) -> Executor:
    """Backward-compatible application entry point."""
    return ExecutorFactory(settings).create()
