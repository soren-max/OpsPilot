from __future__ import annotations

import ipaddress
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.core.command_profiles import CommandAction, OutputParserConfig
from app.core.enums import EnvironmentLevel, IntegrationConfigStatus

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SAFE_ACCOUNT = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]{0,63}$")


def default_status_action() -> list[Literal["status", "start", "stop"]]:
    return ["status"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnvironmentInput(StrictInput):
    name: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    level: EnvironmentLevel


class HostInput(StrictInput):
    id: str | None = Field(default=None, min_length=36, max_length=36)
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    address: str = Field(min_length=1, max_length=253)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_username: str = Field(min_length=1, max_length=64)
    credential_reference: str = Field(
        min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    )

    @field_validator("id")
    @classmethod
    def id_is_uuid(cls, value: str | None) -> str | None:
        if value is not None:
            UUID(value)
        return value

    @field_validator("address")
    @classmethod
    def address_is_literal_or_hostname(cls, value: str) -> str:
        try:
            ipaddress.ip_address(value)
            return value
        except ValueError:
            labels = value.split(".")
            if not labels or any(
                not label
                or len(label) > 63
                or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
                for label in labels
            ):
                raise ValueError("address must be a valid IP address or DNS hostname") from None
            return value

    @field_validator("ssh_username")
    @classmethod
    def username_is_safe(cls, value: str) -> str:
        if not SAFE_ACCOUNT.fullmatch(value):
            raise ValueError("ssh_username contains unsupported characters")
        return value


class ServiceInput(StrictInput):
    id: str | None = Field(default=None, min_length=36, max_length=36)
    name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    host_names: list[str] = Field(min_length=1, max_length=100)

    @field_validator("id")
    @classmethod
    def id_is_uuid(cls, value: str | None) -> str | None:
        if value is not None:
            UUID(value)
        return value

    @field_validator("host_names")
    @classmethod
    def host_names_are_unique_and_safe(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(not SAFE_NAME.fullmatch(item) for item in value):
            raise ValueError("host_names must be unique safe logical host names")
        return value


class ExecutionInput(StrictInput):
    services_sh_remote_path: str = Field(min_length=2, max_length=512)
    working_directory: str = Field(min_length=1, max_length=512)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    status_argv: list[str] = Field(
        default_factory=lambda: ["status", "{service}"], min_length=1, max_length=16
    )
    start_argv: list[str] = Field(default_factory=list, max_length=16)
    stop_argv: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("services_sh_remote_path", "working_directory")
    @classmethod
    def absolute_safe_path(cls, value: str) -> str:
        if not value.startswith("/") or "\x00" in value or "\n" in value or "\r" in value:
            raise ValueError("execution paths must be absolute and contain no control characters")
        if any(part in {"", ".", ".."} for part in value.split("/")[1:]):
            raise ValueError("execution paths must be normalized absolute paths")
        return value

    @field_validator("status_argv")
    @classmethod
    def argv_is_structured_and_safe(cls, value: list[str]) -> list[str]:
        CommandAction(argv=value)
        action_token = value[0].casefold()
        if action_token != "status":
            raise ValueError("status_argv must start with the services.sh status action")
        write_tokens = {
            "start",
            "stop",
            "restart",
            "deploy",
            "delete",
            "remove",
            "enable",
            "disable",
        }
        if any(argument.casefold().lstrip("-") in write_tokens for argument in value):
            raise ValueError("status_argv cannot contain a known write action token")
        return value

    @field_validator("start_argv", "stop_argv")
    @classmethod
    def write_argv_is_structured_and_safe(cls, value: list[str], info: ValidationInfo) -> list[str]:
        if value:
            CommandAction(argv=value)
            expected_action = str(info.field_name).removesuffix("_argv")
            if value[0].casefold() != expected_action:
                raise ValueError(f"{info.field_name} must start with the {expected_action} action")
            if not any("{service}" in argument for argument in value):
                raise ValueError(
                    f"{info.field_name} must explicitly include {{service}}; "
                    "aggregate start/stop requires a separate confirmed contract"
                )
        return value


class AllowlistInput(StrictInput):
    environments: list[str] = Field(min_length=1, max_length=20)
    hosts: list[str] = Field(min_length=1, max_length=100)
    services: list[str] = Field(min_length=1, max_length=200)
    actions: list[Literal["status", "start", "stop"]] = Field(default_factory=default_status_action)

    @model_validator(mode="after")
    def actions_are_safe(self) -> AllowlistInput:
        for values in (self.environments, self.hosts, self.services, self.actions):
            if len(values) != len(set(values)):
                raise ValueError("allowlist values must be unique")
            if any("*" in item or not SAFE_NAME.fullmatch(item) for item in values):
                raise ValueError("allowlist values must be concrete safe identifiers")
        if "status" not in self.actions:
            raise ValueError("status must remain enabled for tests and post-write verification")
        return self


class IntegrationConfigInput(StrictInput):
    environment: EnvironmentInput
    hosts: list[HostInput] = Field(min_length=1, max_length=100)
    services: list[ServiceInput] = Field(min_length=1, max_length=200)
    execution: ExecutionInput
    parser: OutputParserConfig
    allowlist: AllowlistInput

    @field_validator("parser")
    @classmethod
    def parser_is_declarative(cls, value: OutputParserConfig) -> OutputParserConfig:
        if value.type == "custom_python":
            raise ValueError("configuration center cannot load custom Python parsers")
        for pattern in (*value.stdout_regex.values(), *value.stderr_regex.values()):
            if len(pattern) > 512:
                raise ValueError("parser regex must not exceed 512 characters")
            if re.search(r"\\[1-9]|\(\?(?:[=!]|<[=!])", pattern):
                raise ValueError("parser regex cannot use backreferences or lookarounds")
            if re.search(r"\([^)]*[+*][^)]*\)\s*(?:[+*]|\{)", pattern):
                raise ValueError("parser regex cannot contain nested quantifiers")
        return value

    @model_validator(mode="after")
    def aggregate_is_consistent(self) -> IntegrationConfigInput:
        host_names = [item.name for item in self.hosts]
        service_names = [item.name for item in self.services]
        if len(host_names) != len(set(host_names)) or len(service_names) != len(set(service_names)):
            raise ValueError("host and service logical names must be unique")
        if self.allowlist.environments != [self.environment.code]:
            raise ValueError("environment allowlist must exactly match the configured environment")
        if set(self.allowlist.hosts) != set(host_names):
            raise ValueError("host allowlist must exactly match configured hosts")
        if set(self.allowlist.services) != set(service_names):
            raise ValueError("service allowlist must exactly match configured services")
        if any(name not in set(host_names) for item in self.services for name in item.host_names):
            raise ValueError("service association references an unknown host")
        for action in ("start", "stop"):
            argv = getattr(self.execution, f"{action}_argv")
            if action in self.allowlist.actions and not argv:
                raise ValueError(f"enabled action {action} requires an explicit {action}_argv")
        return self


class CredentialCreate(StrictInput):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    private_key: str = Field(min_length=64, max_length=65536)


class IntegrationConfigRead(BaseModel):
    id: str
    environment_id: str
    status: IntegrationConfigStatus
    enabled: bool
    environment: EnvironmentInput
    hosts: list[dict[str, object]]
    services: list[dict[str, object]]
    execution: ExecutionInput
    parser: OutputParserConfig
    allowlist: AllowlistInput
    validation_errors: list[str]
    last_ssh_test_ok: bool
    last_status_test_ok: bool
    last_test_details: dict[str, object]
