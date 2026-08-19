from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from app.core.command_profiles import CommandProfile, OutputParserConfig
from app.core.config_types import ExecutorName

PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
SENSITIVE_KEYS = {"password", "token", "secret", "private_key", "private_key_path"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnvironmentSection(StrictModel):
    name: str = Field(min_length=1)
    mode: Literal["mock", "integration-test", "production"]
    description: str = ""


class ExecutorSection(StrictModel):
    type: ExecutorName = "mock"
    timeout: int = Field(default=30, ge=1, le=300)
    retry: int = Field(default=0, ge=0, le=5)
    concurrency: int = Field(default=4, ge=1, le=32)
    partial_failure_policy: Literal["NONE", "BEST_EFFORT"] = "NONE"


class DatabaseSection(StrictModel):
    url: str | None = None


class ServerSection(StrictModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)


class AnsibleSection(StrictModel):
    inventory_path: str | None = None
    playbook_path: str | None = None
    playbook_directory: str | None = None
    working_directory: str | None = None
    binary_path: str | None = None
    tags: str | None = None


class SshSection(StrictModel):
    enabled: bool = False
    host: str | None = None
    port: int = Field(default=22, ge=1, le=65535)
    user: str | None = None
    username: str | None = None
    private_key_path: str | None = None
    private_key: str | None = None
    timeout: int = Field(default=10, ge=1, le=300)
    known_hosts_path: str | None = None
    jump_mode: str | None = None
    jump_host: str | None = None


class ServicesSection(StrictModel):
    script_path: str | None = None
    working_directory: str | None = None
    command_profile: str = "pending-confirmation"
    output_parser: str = "raw_output"
    allowed_actions: list[Literal["status", "start", "stop"]] | None = None
    environment: dict[
        Literal[
            "HOME",
            "PATH",
            "LANG",
            "LC_ALL",
            "ANSIBLE_CONFIG",
            "SSH_AUTH_SOCK",
        ],
        str,
    ] = Field(default_factory=dict)
    start_script_path: str | None = None
    stop_script_path: str | None = None


class RemoteSection(StrictModel):
    working_directory: str | None = None


class SecuritySection(StrictModel):
    write_enabled: bool = False
    write_operations_enabled: bool | None = None
    production_enabled: bool = False
    production_operations_enabled: bool | None = None
    dry_run_only: bool = True
    execution_acknowledged: bool = False
    approval_required_for_write: bool = True

    @property
    def effective_write_enabled(self) -> bool:
        return (
            self.write_operations_enabled
            if self.write_operations_enabled is not None
            else self.write_enabled
        )

    @property
    def effective_production_enabled(self) -> bool:
        return (
            self.production_operations_enabled
            if self.production_operations_enabled is not None
            else self.production_enabled
        )


class ApprovalSection(StrictModel):
    required_for_write: bool = True
    allow_self_approval: bool = False
    minimum_approvers: int = Field(default=1, ge=1, le=10)


class AllowlistSection(StrictModel):
    environments: list[str] = Field(default_factory=list)
    hosts: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=lambda: ["status"])


class EnvironmentConfig(StrictModel):
    environment: EnvironmentSection
    executor: ExecutorSection
    database: DatabaseSection = Field(default_factory=DatabaseSection)
    server: ServerSection = Field(default_factory=ServerSection)
    ansible: AnsibleSection = Field(default_factory=AnsibleSection)
    ssh: SshSection = Field(default_factory=SshSection)
    remote: RemoteSection = Field(default_factory=RemoteSection)
    services: ServicesSection = Field(default_factory=ServicesSection)
    security: SecuritySection = Field(default_factory=SecuritySection)
    approval: ApprovalSection = Field(default_factory=ApprovalSection)
    allowlist: AllowlistSection = Field(default_factory=AllowlistSection)
    command_profiles: dict[str, CommandProfile] = Field(default_factory=dict)
    output_parsers: dict[str, OutputParserConfig] = Field(default_factory=dict)

    @property
    def normalized_mode(self) -> Literal["mock", "integration-test", "production"]:
        return self.environment.mode


def _reject_sensitive_yaml(value: object, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            item_path = f"{path}.{key}" if path else str(key)
            is_injected_key_path = (
                normalized in {"private_key", "private_key_path"}
                and isinstance(item, str)
                and PLACEHOLDER.fullmatch(item)
            )
            if normalized in SENSITIVE_KEYS and item not in (None, "") and not is_injected_key_path:
                raise ValueError(f"Sensitive field is forbidden in environment YAML: {item_path}")
            _reject_sensitive_yaml(item, item_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_sensitive_yaml(item, f"{path}[{index}]")


def _expand_placeholders(value: object, environ: Mapping[str, str]) -> object:
    if isinstance(value, dict):
        return {key: _expand_placeholders(item, environ) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_placeholders(item, environ) for item in value]
    if isinstance(value, str):
        return PLACEHOLDER.sub(lambda match: environ.get(match.group(1), match.group(0)), value)
    return value


def reject_nested_config_overrides(environ: Mapping[str, str]) -> None:
    """Reject the legacy untyped override channel before any value is applied."""
    prefix = "OPSPILOT_CONFIG__"
    for key in environ:
        if not key.startswith(prefix):
            continue
        path = [part.lower() for part in key.removeprefix(prefix).split("__") if part]
        if not path:
            continue
        raise ValueError(f"Nested configuration environment overrides are forbidden: {key}")


def load_environment_config(
    path: str | Path,
    environ: Mapping[str, str] | None = None,
) -> EnvironmentConfig:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Environment configuration file does not exist: {source}")
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Environment configuration must contain a YAML mapping")
    services = raw.get("services")
    if isinstance(services, dict):
        legacy_fields = sorted(
            {"start_command_profile", "stop_command_profile"}.intersection(services)
        )
        if legacy_fields:
            raise ValueError(
                "Unsupported legacy services fields: "
                + ", ".join(f"services.{name}" for name in legacy_fields)
                + "; use command_profiles.<profile>.actions.status/start/stop.argv"
            )
    _reject_sensitive_yaml(raw)
    env = environ if environ is not None else os.environ
    expanded = _expand_placeholders(raw, env)
    if not isinstance(expanded, dict):
        raise ValueError("Environment configuration must contain a YAML mapping")
    reject_nested_config_overrides(env)
    config = EnvironmentConfig.model_validate(expanded)
    acknowledged = str(env.get("OPSPILOT_EXECUTION_ACKNOWLEDGED", "")).lower() == "true"
    if config.security.effective_production_enabled and not acknowledged:
        raise ValueError("Production operations require OPSPILOT_EXECUTION_ACKNOWLEDGED=true")
    real_test_execution = (
        config.normalized_mode == "integration-test"
        and config.executor.type == "ansible"
        and not config.security.dry_run_only
    )
    if real_test_execution and (
        not config.security.effective_write_enabled
        or config.security.effective_production_enabled
        or not acknowledged
    ):
        raise ValueError(
            "Real test execution requires write_enabled, production disabled, "
            "and OPSPILOT_EXECUTION_ACKNOWLEDGED=true"
        )
    return config
