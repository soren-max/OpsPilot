from __future__ import annotations

import importlib
import re
from string import Formatter
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.parsers.base import StatusOutputParser

ALLOWED_PLACEHOLDERS = {"environment", "host", "service"}
FORBIDDEN_EXECUTION_TOKENS = {"ansible", "ansible-playbook"}
VALID_STATES = {
    "running",
    "stopped",
    "failed",
    "unreachable",
    "unknown",
    "not_found",
    "timeout",
    "parse_failed",
}


class StrictProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CommandAction(StrictProfileModel):
    argv: list[str]

    @field_validator("argv")
    @classmethod
    def validate_argv(cls, value: list[str]) -> list[str]:
        for argument in value:
            if not isinstance(argument, str) or "\x00" in argument:
                raise ValueError("action argv must contain strings without NUL bytes")
            try:
                fields = {
                    field_name
                    for _, field_name, _, _ in Formatter().parse(argument)
                    if field_name is not None
                }
            except ValueError as exc:
                raise ValueError("action argv contains malformed placeholders") from exc
            unknown = fields - ALLOWED_PLACEHOLDERS
            if unknown:
                raise ValueError(
                    "action argv contains unsupported placeholders: " + ", ".join(sorted(unknown))
                )
            normalized = argument.casefold()
            if (
                normalized.rsplit("/", 1)[-1] in FORBIDDEN_EXECUTION_TOKENS
                or normalized.endswith((".yml", ".yaml"))
            ):
                raise ValueError(
                    "action argv must describe the services.sh contract, not Ansible or a Playbook"
                )
        return value


class CommandProfile(StrictProfileModel):
    capabilities: list[Literal["status", "start", "stop"]]
    parser: str
    actions: dict[Literal["status", "start", "stop"], CommandAction]

    @model_validator(mode="after")
    def validate_capabilities(self) -> CommandProfile:
        if not self.capabilities:
            raise ValueError("profile capabilities must be explicit and non-empty")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("profile capabilities must be unique")
        return self


class OutputParserConfig(StrictProfileModel):
    type: Literal["json", "regex", "legacy_text", "raw", "custom_python"]
    exit_code_map: dict[int, str] = Field(default_factory=dict)
    stdout_regex: dict[str, str] = Field(default_factory=dict)
    stderr_regex: dict[str, str] = Field(default_factory=dict)
    conflict_policy: Literal["failed", "first", "last"] = "failed"
    default_state: str = "unknown"
    custom_parser: str | None = None

    @model_validator(mode="after")
    def validate_parser(self) -> OutputParserConfig:
        states = {
            *self.exit_code_map.values(),
            *self.stdout_regex.keys(),
            *self.stderr_regex.keys(),
            self.default_state,
        }
        unknown = states - VALID_STATES
        if unknown:
            raise ValueError("parser contains unsupported states: " + ", ".join(sorted(unknown)))
        for pattern in (*self.stdout_regex.values(), *self.stderr_regex.values()):
            re.compile(pattern)
        if self.type == "custom_python" and not self.custom_parser:
            raise ValueError("custom_python parser requires custom_parser")
        if self.type != "custom_python" and self.custom_parser:
            raise ValueError("custom_parser is only valid for custom_python")
        return self


def load_custom_parser(import_path: str) -> StatusOutputParser:
    """Load a local parser class by dotted path; configuration never contains source code."""
    module_name, separator, class_name = import_path.rpartition(".")
    if not separator or not module_name.startswith("app.parsers."):
        raise ValueError("custom parser must be an app.parsers.* class")
    parser_class = getattr(importlib.import_module(module_name), class_name, None)
    if parser_class is None:
        raise ValueError(f"Custom parser does not exist: {import_path}")
    parser = parser_class()
    if not callable(getattr(parser, "parse", None)):
        raise ValueError("Custom parser must implement parse(stdout, stderr, exit_code)")
    return cast(StatusOutputParser, parser)
