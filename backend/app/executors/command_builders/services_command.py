from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.command_profiles import CommandAction, CommandProfile
from app.core.enums import OperationAction
from app.executors.base import ExecutionRequest

SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$")
FORBIDDEN_PARAMETER_KEYS = {
    "command",
    "script",
    "script_path",
    "playbook",
    "playbook_path",
    "extra_vars",
    "extra-vars",
}


class CommandProfileNotConfigured(ValueError):
    pass


class UnknownCommandProfile(ValueError):
    pass


@dataclass(frozen=True)
class ServicesCommandBuilder:
    """Render configuration-owned arguments after the fixed services.script_path."""

    script_path: str
    command_profile: str
    profiles: dict[str, CommandProfile] = field(default_factory=dict)

    @property
    def profile(self) -> CommandProfile:
        if self.command_profile in {"", "pending-confirmation"}:
            raise CommandProfileNotConfigured("services.sh command profile is pending confirmation")
        profile = self.profiles.get(self.command_profile)
        if profile is not None:
            return profile
        # Compatibility for the old status-only safety fixture while deployments migrate.
        if self.command_profile == "test-fixture-v1":
            return CommandProfile(
                capabilities=["status"],
                parser="json_status",
                actions={
                    "status": CommandAction(argv=["status", "{environment}", "{host}", "{service}"])
                },
            )
        raise UnknownCommandProfile(f"Unknown services.sh command profile: {self.command_profile}")

    @property
    def capabilities(self) -> frozenset[OperationAction]:
        profile = self.profile
        return frozenset(
            OperationAction(value) for value in profile.capabilities if value in profile.actions
        )

    def validate(self) -> None:
        profile = self.profile
        if self.command_profile.startswith("test-fixture") and Path(self.script_path).name != (
            "fake_services.sh"
        ):
            raise ValueError(f"{self.command_profile} is restricted to fake_services.sh")
        # Force every action template through the same renderer used at execution.
        for template in profile.actions.values():
            self._render(template, "environment", "host", "service")

    def build(self, request: ExecutionRequest) -> list[str]:
        for label, value in (
            ("environment", request.environment_code),
            ("host", request.host_name),
            ("service", request.service_name),
        ):
            if not SAFE_IDENTIFIER.fullmatch(value):
                raise ValueError(f"{label} contains unsupported characters")
        forbidden = FORBIDDEN_PARAMETER_KEYS.intersection(key.lower() for key in request.parameters)
        if forbidden:
            raise ValueError(
                "Execution parameters contain forbidden command fields: "
                + ", ".join(sorted(forbidden))
            )
        if request.parameters:
            raise ValueError("Local services execution does not accept user parameters")
        profile = self.profile
        if request.action.value not in profile.capabilities:
            if self.command_profile == "test-fixture-v1":
                raise CommandProfileNotConfigured(
                    f"services.sh {request.action.value} command profile is pending confirmation"
                )
            raise ValueError("Action is not declared in command profile capabilities")
        template = profile.actions.get(request.action.value)
        if template is None:
            raise ValueError("Command profile does not define this action template")
        self.validate()
        return [
            self.script_path,
            *self._render(
                template,
                request.environment_code,
                request.host_name,
                request.service_name,
            ),
        ]

    def build_status_command(self, request: ExecutionRequest) -> list[str]:
        return self.build(request)

    def build_start_command(self, request: ExecutionRequest) -> list[str]:
        return self.build(request)

    def build_stop_command(self, request: ExecutionRequest) -> list[str]:
        return self.build(request)

    @staticmethod
    def _render(
        template: CommandAction,
        environment: str,
        host: str,
        service: str,
    ) -> list[str]:
        values = {"environment": environment, "host": host, "service": service}
        return [argument.format_map(values) for argument in template.argv]
