from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings; transport details remain operator-owned by Ansible."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="OPSPILOT_", extra="ignore")

    app_name: str = "OpsPilot"
    environment: str = "development"
    database_url: str = Field(
        default="sqlite:///./opspilot_ops.db",
        validation_alias=AliasChoices("DATABASE_URL", "OPSPILOT_DATABASE_URL"),
    )
    executor: str = "mock"
    write_operations_enabled: bool = False
    production_operations_enabled: bool = False
    dry_run_only: bool = True
    execution_acknowledged: bool = False
    ansible_inventory_path: str | None = None
    ansible_playbook_directory: str | None = None
    ansible_binary_path: str | None = None
    execution_timeout_seconds: int = Field(default=30, ge=1, le=300)
    executor_retry: int = Field(default=0, ge=0, le=5)
    partial_failure_policy: str = "NONE"
    rbac_enabled: bool = True
    approval_required_for_write: bool = True
    allow_self_approval: bool = False
    minimum_approvers: int = Field(default=1, ge=1, le=10)
    stale_task_seconds: int = Field(default=300, ge=10, le=86_400)
    lock_ttl_seconds: int = Field(default=900, ge=30, le=86_400)
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=60)
    workflow_checkpoint_backend: str = "memory"
    prometheus_base_url: str | None = None
    prometheus_auth_token: SecretStr | None = None
    loki_base_url: str | None = None
    loki_auth_token: SecretStr | None = None
    loki_tenant: str | None = Field(default=None, max_length=120)
    capability_timeout_seconds: float = Field(default=5.0, ge=0.1, le=30)
    capability_max_time_range_seconds: int = Field(default=3600, ge=60, le=86_400)
    capability_max_log_entries: int = Field(default=100, ge=1, le=1000)
    capability_max_metric_series: int = Field(default=20, ge=1, le=100)
    capability_minimum_step_seconds: int = Field(default=15, ge=1, le=3600)
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

    @field_validator("prometheus_base_url", "loki_base_url", mode="before")
    @classmethod
    def validate_operator_base_url(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("Observability base URLs must be strings")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Observability base URLs must be credential-free HTTP(S) origins")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_portable_execution(self) -> "Settings":
        if len(self.secret_key) < 32:
            raise ValueError("OPSPILOT_SECRET_KEY must contain at least 32 characters")
        if self.default_admin_enabled and len(self.default_admin_password) < 12:
            raise ValueError(
                "DEFAULT_ADMIN_PASSWORD must contain at least 12 characters when enabled"
            )
        if self.selected_executor not in {"mock", "ansible"}:
            raise ValueError("OPSPILOT_EXECUTOR must be mock or ansible")
        if self.partial_failure_policy not in {"NONE", "BEST_EFFORT"}:
            raise ValueError("OPSPILOT_PARTIAL_FAILURE_POLICY must be NONE or BEST_EFFORT")
        if self.workflow_checkpoint_backend != "memory":
            raise ValueError(
                "M2 supports the memory workflow checkpointer only; "
                "durable Postgres is planned for M4"
            )
        if self.production_operations_enabled and not self.write_operations_enabled:
            raise ValueError(
                "OPSPILOT_PRODUCTION_OPERATIONS_ENABLED requires write operations"
            )
        if self.selected_executor == "mock" and not self.dry_run_only:
            raise ValueError("Mock backend requires dry-run mode")
        if self.selected_executor == "ansible":
            missing = [
                name
                for name, value in {
                    "OPSPILOT_ANSIBLE_INVENTORY_PATH": self.ansible_inventory_path,
                    "OPSPILOT_ANSIBLE_PLAYBOOK_DIRECTORY": self.ansible_playbook_directory,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError("Ansible backend requires: " + ", ".join(missing))
            if not self.execution_acknowledged:
                raise ValueError("Ansible backend requires explicit execution acknowledgement")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def selected_executor(self) -> str:
        return self.executor



@lru_cache
def get_settings() -> Settings:
    return Settings()
