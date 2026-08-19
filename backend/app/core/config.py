import os
from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.command_profiles import CommandProfile, OutputParserConfig
from app.core.config_types import ExecutionMode, ExecutorName
from app.core.environment_config import (
    EnvironmentConfig,
    load_environment_config,
    reject_nested_config_overrides,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="OPSPILOT_", extra="ignore")

    app_name: str = "OpsPilot"
    environment: str = "development"
    environment_mode: ExecutionMode = "mock"
    environment_config_path: str | None = None
    database_url: str = Field(
        default="sqlite:///./opspilot_ops.db",
        validation_alias=AliasChoices("DATABASE_URL", "OPSPILOT_DATABASE_URL"),
    )
    executor: ExecutorName = "mock"
    executor_type: ExecutorName | None = None
    write_operations_enabled: bool = False
    production_operations_enabled: bool = False
    dry_run_only: bool = True
    test_execution_acknowledged: bool | None = None
    execution_acknowledged: bool = False
    allowed_environments: str = ""
    allowed_hosts: str = ""
    allowed_services: str = ""
    allowed_actions: str = "status"
    ssh_host: str | None = None
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_user: str | None = None
    ssh_username: str | None = None
    ssh_private_key_path: str | None = None
    ssh_jump_mode: str | None = None
    ssh_jump_host: str | None = None
    ssh_known_hosts_path: str | None = None
    credential_directory: str = "/home/opspilot/.ssh"
    services_script_path: str | None = None
    services_working_directory: str | None = None
    services_command_profile: str = "pending-confirmation"
    services_start_command_profile: str | None = None
    services_stop_command_profile: str | None = None
    services_output_parser: str = "raw_output"
    services_environment: dict[str, str] = Field(default_factory=dict)
    services_start_script_path: str | None = None
    services_stop_script_path: str | None = None
    ansible_inventory_path: str | None = None
    ansible_playbook_path: str | None = None
    ansible_playbook_directory: str | None = None
    ansible_working_directory: str | None = None
    ansible_tags: str | None = None
    ansible_binary_path: str | None = None
    test_runtime_directory: str | None = None
    execution_timeout_seconds: int = Field(default=30, ge=1, le=300)
    executor_retry: int = Field(default=0, ge=0, le=5)
    batch_concurrency_limit: int = Field(default=4, ge=1, le=32)
    partial_failure_policy: str = "NONE"
    redis_url: str | None = None
    redis_queue_name: str = "opspilot-ops-tasks"
    rbac_enabled: bool = True
    approval_required_for_write: bool = True
    allow_self_approval: bool = False
    minimum_approvers: int = Field(default=1, ge=1, le=10)
    command_profiles: dict[str, CommandProfile] = Field(default_factory=dict)
    output_parsers: dict[str, OutputParserConfig] = Field(default_factory=dict)
    max_output_bytes: int = Field(default=262_144, ge=1024, le=10_485_760)
    termination_grace_seconds: float = Field(default=2.0, ge=0.1, le=30)
    stale_task_seconds: int = Field(default=300, ge=10, le=86_400)
    lock_ttl_seconds: int = Field(default=900, ge=30, le=86_400)
    ops_adapter_path: str | None = None
    script_adapter_path: str | None = None
    script_runtime_dir: str | None = None
    ssh_connect_timeout_seconds: int = Field(default=10, ge=1, le=300)
    remote_working_directory: str | None = None
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=60)
    login_failure_limit: int = Field(default=5, ge=2, le=20)
    login_failure_window_seconds: int = Field(default=300, ge=10, le=3600)
    login_lockout_seconds: int = Field(default=300, ge=10, le=3600)
    server_host: str = "127.0.0.1"
    server_port: int = Field(default=8000, ge=1, le=65535)
    secret_key: str = ""
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    log_file: str | None = None
    default_admin_username: str = Field(
        default="admin",
        validation_alias=AliasChoices("DEFAULT_ADMIN_USERNAME", "OPSPILOT_DEFAULT_ADMIN_USERNAME"),
    )
    default_admin_password: str = Field(
        default="",
        validation_alias=AliasChoices("DEFAULT_ADMIN_PASSWORD", "OPSPILOT_DEFAULT_ADMIN_PASSWORD"),
    )
    default_admin_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEFAULT_ADMIN_ENABLED", "OPSPILOT_DEFAULT_ADMIN_ENABLED"),
    )

    @model_validator(mode="after")
    def validate_execution_mode(self) -> "Settings":
        reject_nested_config_overrides(os.environ)
        if len(self.secret_key) < 32:
            raise ValueError("OPSPILOT_SECRET_KEY must contain at least 32 characters")
        if self.default_admin_enabled and len(self.default_admin_password) < 12:
            raise ValueError(
                "DEFAULT_ADMIN_PASSWORD must contain at least 12 characters when enabled"
            )
        if self.environment_config_path:
            self._apply_environment_config(
                load_environment_config(self.environment_config_path),
                self.model_fields_set,
            )
        legacy_fields = [
            name
            for name in (
                "services_start_command_profile",
                "services_stop_command_profile",
            )
            if getattr(self, name) is not None
        ]
        if legacy_fields:
            raise ValueError(
                "Unsupported legacy OPSPILOT settings: "
                + ", ".join(name.upper() for name in legacy_fields)
                + "; use command_profiles.<profile>.actions.status/start/stop.argv"
            )
        if self.test_execution_acknowledged is not None:
            raise ValueError(
                "OPSPILOT_TEST_EXECUTION_ACKNOWLEDGED is obsolete; "
                "use OPSPILOT_EXECUTION_ACKNOWLEDGED for integration-test mode"
            )
        supported_actions = {"status", "start", "stop"}
        unsupported_actions = self.allowed_action_set - supported_actions
        if unsupported_actions:
            raise ValueError(
                "OPSPILOT_ALLOWED_ACTIONS contains unsupported actions: "
                + ", ".join(sorted(unsupported_actions))
            )
        if self.partial_failure_policy not in {"NONE", "BEST_EFFORT"}:
            raise ValueError("OPSPILOT_PARTIAL_FAILURE_POLICY must be NONE or BEST_EFFORT")
        if self.production_operations_enabled and not self.write_operations_enabled:
            raise ValueError(
                "OPSPILOT_PRODUCTION_OPERATIONS_ENABLED requires "
                "OPSPILOT_WRITE_OPERATIONS_ENABLED=true"
            )
        if self.environment_mode == "production":
            if self.allow_self_approval:
                raise ValueError("Production mode forbids self approval")
            if self.write_operations_enabled:
                required = {
                    "OPSPILOT_EXECUTOR=local_services": self.selected_executor == "local_services",
                    "OPSPILOT_PRODUCTION_OPERATIONS_ENABLED=true": (
                        self.production_operations_enabled
                    ),
                    "OPSPILOT_DRY_RUN_ONLY=false": not self.dry_run_only,
                    "OPSPILOT_EXECUTION_ACKNOWLEDGED=true": self.execution_is_acknowledged,
                    "OPSPILOT_APPROVAL_REQUIRED_FOR_WRITE=true": self.approval_required_for_write,
                    "OPSPILOT_SERVICES_SCRIPT_PATH": bool(self.services_script_path),
                }
                invalid = [label for label, valid in required.items() if not valid]
                if invalid:
                    raise ValueError("Production write execution requires: " + ", ".join(invalid))
            return self
        if self.environment_mode == "mock":
            if not self.dry_run_only:
                raise ValueError("Mock mode requires OPSPILOT_DRY_RUN_ONLY=true")
            return self

        if self.dry_run_only:
            if self.selected_executor not in {
                "mock",
                "dry_run",
                "script",
                "local_script",
                "local_services",
                "ssh_script",
                "ansible",
                "ansible_playbook",
            }:
                raise ValueError(
                    "Dry-run integration-test permits only configured executor adapters"
                )
            if self.write_operations_enabled or self.production_operations_enabled:
                raise ValueError("Dry-run integration-test cannot enable write or production")
            return self

        if self.selected_executor in {"script", "local_script", "ssh_script"}:
            raise ValueError(
                "Legacy script and SSH executors are disabled for real execution; "
                "use local_services"
            )

        if self.selected_executor == "local_services":
            required = {
                "OPSPILOT_ENVIRONMENT_MODE=integration-test": (
                    self.environment_mode == "integration-test"
                ),
                "OPSPILOT_PRODUCTION_OPERATIONS_ENABLED=false": (
                    not self.production_operations_enabled
                ),
                "OPSPILOT_DRY_RUN_ONLY=false": not self.dry_run_only,
                "OPSPILOT_EXECUTION_ACKNOWLEDGED=true": self.execution_is_acknowledged,
                "OPSPILOT_SERVICES_SCRIPT_PATH": bool(self.services_script_path),
            }
            invalid = [label for label, valid in required.items() if not valid]
            if invalid:
                raise ValueError("ScriptExecutor execution requires: " + ", ".join(invalid))
            self._validate_real_allowlists(script_only=True)
            return self

        if self.selected_executor in {"ansible", "ansible_playbook"}:
            if self.write_operations_enabled or self.production_operations_enabled:
                raise ValueError("AnsiblePlaybookExecutor is not enabled in this phase")
            return self

        required = {
            "OPSPILOT_EXECUTOR_TYPE=ansible": self.selected_executor == "ansible",
            "OPSPILOT_WRITE_OPERATIONS_ENABLED=true": self.write_operations_enabled,
            "OPSPILOT_PRODUCTION_OPERATIONS_ENABLED=false": not self.production_operations_enabled,
            "OPSPILOT_DRY_RUN_ONLY=false": not self.dry_run_only,
            "OPSPILOT_EXECUTION_ACKNOWLEDGED=true": self.execution_is_acknowledged,
        }
        invalid = [label for label, valid in required.items() if not valid]
        if invalid:
            raise ValueError(
                "integration-test execution requires all safety acknowledgements: "
                + ", ".join(invalid)
            )
        configured_paths = {
            "OPSPILOT_ANSIBLE_BINARY_PATH": self.ansible_binary_path,
            "OPSPILOT_ANSIBLE_INVENTORY_PATH": self.ansible_inventory_path,
            "OPSPILOT_ANSIBLE_PLAYBOOK_DIRECTORY": self.ansible_playbook_directory,
            "OPSPILOT_ANSIBLE_WORKING_DIRECTORY": self.ansible_working_directory,
            "OPSPILOT_SERVICES_SCRIPT_PATH": self.services_script_path,
            "OPSPILOT_TEST_RUNTIME_DIRECTORY": self.test_runtime_directory,
        }
        missing_paths = [name for name, value in configured_paths.items() if not value]
        if missing_paths:
            raise ValueError(
                "integration-test execution requires fixed paths: " + ", ".join(missing_paths)
            )
        self._validate_real_allowlists(script_only=False)
        return self

    def _validate_real_allowlists(self, script_only: bool) -> None:
        allowlists = {
            "OPSPILOT_ALLOWED_ENVIRONMENTS": self.allowed_environment_set,
            "OPSPILOT_ALLOWED_HOSTS": self.allowed_host_set,
            "OPSPILOT_ALLOWED_SERVICES": self.allowed_service_set,
            "OPSPILOT_ALLOWED_ACTIONS": self.allowed_action_set,
        }
        missing_allowlists = [name for name, values in allowlists.items() if not values]
        if missing_allowlists:
            # A local_services deployment may bootstrap only the fixed wrapper and
            # platform security controls. Runtime target/action allowlists then come
            # from a validated, tested and enabled database configuration. Empty
            # static allowlists still fail closed when no dynamic config is active.
            dynamic_bootstrap = (
                script_only
                and bool(self.allowed_action_set)
                and self.allowed_action_set <= {"status", "start", "stop"}
            )
            if dynamic_bootstrap:
                return
            raise ValueError(
                "integration-test execution requires non-empty allowlists: "
                + ", ".join(missing_allowlists)
            )
        if any("*" in value for values in allowlists.values() for value in values):
            raise ValueError("Wildcards are forbidden in integration-test allowlists")
        supported_actions = {"status", "start", "stop"}
        unsupported_actions = self.allowed_action_set - supported_actions
        if unsupported_actions:
            raise ValueError(
                "OPSPILOT_ALLOWED_ACTIONS contains unsupported actions: "
                + ", ".join(sorted(unsupported_actions))
            )

    def _apply_environment_config(
        self,
        config: EnvironmentConfig,
        explicit_fields: set[str],
    ) -> None:
        """Overlay YAML values while preserving explicit OPSPILOT_* environment overrides."""
        values: dict[str, object | None] = {
            "environment": config.environment.name,
            "environment_mode": config.normalized_mode,
            "database_url": config.database.url,
            "executor_type": config.executor.type,
            "execution_timeout_seconds": config.executor.timeout,
            "executor_retry": config.executor.retry,
            "batch_concurrency_limit": config.executor.concurrency,
            "partial_failure_policy": config.executor.partial_failure_policy,
            "ansible_inventory_path": config.ansible.inventory_path,
            "ansible_playbook_path": config.ansible.playbook_path,
            "ansible_playbook_directory": config.ansible.playbook_directory,
            "ansible_working_directory": config.ansible.working_directory,
            "ansible_binary_path": config.ansible.binary_path,
            "ansible_tags": config.ansible.tags,
            "ssh_host": config.ssh.host,
            "ssh_port": config.ssh.port,
            "ssh_user": config.ssh.user or config.ssh.username,
            "ssh_username": config.ssh.username,
            "ssh_private_key_path": (config.ssh.private_key_path or config.ssh.private_key),
            "ssh_connect_timeout_seconds": config.ssh.timeout,
            "ssh_known_hosts_path": config.ssh.known_hosts_path,
            "ssh_jump_mode": config.ssh.jump_mode,
            "ssh_jump_host": config.ssh.jump_host,
            "remote_working_directory": config.remote.working_directory,
            "services_script_path": config.services.script_path,
            "services_working_directory": config.services.working_directory,
            "services_command_profile": config.services.command_profile,
            "services_output_parser": config.services.output_parser,
            "services_environment": config.services.environment,
            "services_start_script_path": config.services.start_script_path,
            "services_stop_script_path": config.services.stop_script_path,
            "write_operations_enabled": config.security.effective_write_enabled,
            "production_operations_enabled": config.security.effective_production_enabled,
            "dry_run_only": config.security.dry_run_only,
            "execution_acknowledged": config.security.execution_acknowledged,
            "approval_required_for_write": config.approval.required_for_write,
            "allow_self_approval": config.approval.allow_self_approval,
            "minimum_approvers": config.approval.minimum_approvers,
            "command_profiles": config.command_profiles,
            "output_parsers": config.output_parsers,
            "allowed_environments": ",".join(config.allowlist.environments),
            "allowed_hosts": ",".join(config.allowlist.hosts),
            "allowed_services": ",".join(config.allowlist.services),
            "allowed_actions": ",".join(
                config.services.allowed_actions or config.allowlist.actions
            ),
            "server_host": config.server.host,
            "server_port": config.server.port,
        }
        for field_name, value in values.items():
            if field_name not in explicit_fields and value is not None:
                object.__setattr__(self, field_name, value)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def selected_executor(self) -> ExecutorName:
        return self.executor_type or self.executor

    @staticmethod
    def _csv_set(value: str) -> frozenset[str]:
        return frozenset(item.strip() for item in value.split(",") if item.strip())

    @property
    def allowed_environment_set(self) -> frozenset[str]:
        return self._csv_set(self.allowed_environments)

    @property
    def allowed_host_set(self) -> frozenset[str]:
        return self._csv_set(self.allowed_hosts)

    @property
    def allowed_service_set(self) -> frozenset[str]:
        return self._csv_set(self.allowed_services)

    @property
    def allowed_action_set(self) -> frozenset[str]:
        return self._csv_set(self.allowed_actions)

    @property
    def real_integration_execution_enabled(self) -> bool:
        return (
            self.environment_mode == "integration-test"
            and self.selected_executor in {"ansible", "ansible_playbook", "local_services"}
            and (self.selected_executor == "local_services" or self.write_operations_enabled)
            and not self.production_operations_enabled
            and not self.dry_run_only
            and self.execution_is_acknowledged
            and (
                self.selected_executor != "local_services"
                or self.services_command_profile not in {"", "pending-confirmation"}
            )
        )

    @property
    def real_script_execution_enabled(self) -> bool:
        return (
            self.real_integration_execution_enabled and self.selected_executor == "local_services"
        )

    @property
    def execution_is_acknowledged(self) -> bool:
        return self.execution_acknowledged

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"development", "dev", "local", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
