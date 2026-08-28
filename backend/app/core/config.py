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
    deployment_config_path: str | None = None
    deployment_playbook_directory: str | None = None
    execution_timeout_seconds: int = Field(default=30, ge=1, le=300)
    execution_dispatch_lease_seconds: int = Field(default=60, ge=10, le=3600)
    harness_base_url: str | None = None
    harness_account_id: str | None = Field(default=None, max_length=120)
    harness_org_id: str | None = Field(default=None, max_length=120)
    harness_project_id: str | None = Field(default=None, max_length=120)
    harness_api_key: SecretStr | None = None
    harness_restart_pipeline_identifier: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_-]{1,120}$"
    )
    executor_retry: int = Field(default=0, ge=0, le=5)
    partial_failure_policy: str = "NONE"
    rbac_enabled: bool = True
    approval_required_for_write: bool = True
    allow_self_approval: bool = False
    minimum_approvers: int = Field(default=1, ge=1, le=10)
    stale_task_seconds: int = Field(default=300, ge=10, le=86_400)
    lock_ttl_seconds: int = Field(default=900, ge=30, le=86_400)
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=60)
    workflow_checkpoint_backend: str = "auto"
    memory_backend: str = "disabled"
    qdrant_base_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = Field(
        default="opspilot_incident_memory_v1", min_length=1, max_length=120
    )
    memory_retrieval_limit: int = Field(default=5, ge=1, le=10)
    mcp_http_host: str = "127.0.0.1"
    mcp_http_port: int = Field(default=8010, ge=1, le=65535)
    mcp_auth_issuer: str | None = None
    mcp_auth_audience: str | None = None
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
    llm_mode: str = Field(
        default="deterministic",
        validation_alias=AliasChoices("LLM_MODE", "OPSPILOT_LLM_MODE"),
    )
    llm_provider: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_PROVIDER", "OPSPILOT_LLM_PROVIDER"),
    )
    llm_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_MODEL", "OPSPILOT_LLM_MODEL"),
    )
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "OPSPILOT_LLM_API_KEY"),
    )
    llm_timeout_seconds: float = Field(
        default=30,
        ge=1,
        le=120,
        validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "OPSPILOT_LLM_TIMEOUT_SECONDS"),
    )
    llm_max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        validation_alias=AliasChoices("LLM_MAX_RETRIES", "OPSPILOT_LLM_MAX_RETRIES"),
    )
    llm_mutating_action_min_confidence: float = Field(
        default=0.8,
        ge=0,
        le=1,
        validation_alias=AliasChoices(
            "LLM_MUTATING_ACTION_MIN_CONFIDENCE",
            "OPSPILOT_LLM_MUTATING_ACTION_MIN_CONFIDENCE",
        ),
    )
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

    @field_validator(
        "prometheus_base_url",
        "loki_base_url",
        "qdrant_base_url",
        "harness_base_url",
        mode="before",
    )
    @classmethod
    def validate_operator_base_url(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("Operator base URLs must be strings")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Operator base URLs must be credential-free HTTP(S) origins")
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
        if self.workflow_checkpoint_backend not in {"auto", "memory", "postgres"}:
            raise ValueError("Workflow checkpoint backend must be auto, memory, or postgres")
        if self.workflow_checkpoint_backend == "postgres" and not self.database_url.startswith(
            "postgres"
        ):
            raise ValueError("Postgres checkpoint backend requires a PostgreSQL database URL")
        if self.memory_backend not in {"disabled", "qdrant"}:
            raise ValueError("Memory backend must be disabled or qdrant")
        if self.memory_backend == "qdrant" and not self.qdrant_base_url:
            raise ValueError("Qdrant memory backend requires OPSPILOT_QDRANT_BASE_URL")
        if self.harness_restart_pipeline_identifier:
            missing_harness = [
                name
                for name, value in {
                    "OPSPILOT_HARNESS_BASE_URL": self.harness_base_url,
                    "OPSPILOT_HARNESS_ACCOUNT_ID": self.harness_account_id,
                    "OPSPILOT_HARNESS_ORG_ID": self.harness_org_id,
                    "OPSPILOT_HARNESS_PROJECT_ID": self.harness_project_id,
                    "OPSPILOT_HARNESS_API_KEY": self.harness_api_key,
                }.items()
                if not value
            ]
            if missing_harness:
                raise ValueError(
                    "Harness execution profile requires: " + ", ".join(missing_harness)
                )
        if self.llm_mode not in {"deterministic", "llm"}:
            raise ValueError("LLM_MODE must be deterministic or llm")
        if self.llm_mode == "llm":
            if self.llm_provider != "openai":
                raise ValueError("LLM_PROVIDER must be openai in M3B")
            missing_llm = [
                name
                for name, value in {
                    "LLM_MODEL": self.llm_model,
                    "LLM_API_KEY": self.llm_api_key,
                }.items()
                if not value
            ]
            if missing_llm:
                raise ValueError("LLM mode requires: " + ", ".join(missing_llm))
        if self.production_operations_enabled and not self.write_operations_enabled:
            raise ValueError("OPSPILOT_PRODUCTION_OPERATIONS_ENABLED requires write operations")
        if self.selected_executor == "mock" and not self.dry_run_only:
            raise ValueError("Mock backend requires dry-run mode")
        if self.selected_executor == "ansible":
            if not self.deployment_config_path:
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
