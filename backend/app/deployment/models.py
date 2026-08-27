from __future__ import annotations

import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.deployment import DeploymentTargetProfile
from app.domain.actions.models import ActionType

SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
SAFE_MAPPING = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}$")
SAFE_CONFIG_PATH = re.compile(r"^[A-Za-z0-9_./-]{1,500}$")
SAFE_ENV_REF = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
SERVICE_OPERATIONS = frozenset(
    {
        ActionType.GET_SERVICE_STATUS,
        ActionType.START_SERVICE,
        ActionType.STOP_SERVICE,
        ActionType.RESTART_SERVICE,
    }
)


class StrictDeploymentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ServiceControlType(StrEnum):
    SYSTEMD = "SYSTEMD"
    FIXED_SCRIPT = "FIXED_SCRIPT"


class VerificationCheckType(StrEnum):
    HTTP_HEALTH = "HTTP_HEALTH"
    SYSTEMD_STATUS = "SYSTEMD_STATUS"
    PROCESS_STATUS = "PROCESS_STATUS"


class ReadinessLevel(StrEnum):
    OBSERVE_READY = "OBSERVE_READY"
    REMEDIATION_READY = "REMEDIATION_READY"
    FULL_INCIDENT_READY = "FULL_INCIDENT_READY"


class AnsibleConnectionProfile(StrictDeploymentModel):
    id: str = Field(pattern=SAFE_REF.pattern)
    inventory_ref: str = Field(pattern=SAFE_REF.pattern)
    host_alias: str = Field(pattern=SAFE_REF.pattern)
    remote_user_ref: str = Field(pattern=SAFE_REF.pattern)
    become_required: bool = False
    connection_timeout: int = Field(default=10, ge=1, le=120)
    credential_env_ref: str | None = Field(default=None, pattern=SAFE_ENV_REF.pattern)


class ServiceControlProfile(StrictDeploymentModel):
    id: str = Field(pattern=SAFE_REF.pattern)
    control_type: ServiceControlType
    service_mapping: dict[str, str] = Field(min_length=1, max_length=100)
    allowed_operations: frozenset[ActionType]
    fixed_script_path: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_bounded_control(self) -> ServiceControlProfile:
        if not self.allowed_operations or not self.allowed_operations <= SERVICE_OPERATIONS:
            raise ValueError("Service control operations must use the fixed service allowlist")
        for semantic_service, mapped_service in self.service_mapping.items():
            if not SAFE_MAPPING.fullmatch(semantic_service):
                raise ValueError("Semantic service mapping contains unsafe characters")
            if not SAFE_MAPPING.fullmatch(mapped_service) or mapped_service.startswith("-"):
                raise ValueError("Mapped service identifier is unsafe")
        if self.control_type is ServiceControlType.FIXED_SCRIPT:
            if self.fixed_script_path is None:
                raise ValueError("FIXED_SCRIPT control requires an operator-owned script path")
            path = PurePosixPath(self.fixed_script_path)
            if (
                not path.is_absolute()
                or ".." in path.parts
                or not SAFE_CONFIG_PATH.fullmatch(self.fixed_script_path)
            ):
                raise ValueError("Fixed script path must be a safe absolute operator path")
        elif self.fixed_script_path is not None:
            raise ValueError("SYSTEMD control cannot define a script path")
        return self


class VerificationCheck(StrictDeploymentModel):
    check_type: VerificationCheckType
    endpoint_ref: str | None = Field(default=None, pattern=SAFE_REF.pattern)
    expected_http_status: int | None = Field(default=None, ge=100, le=599)
    expected_service_state: Literal["running", "stopped"] | None = None
    required: bool = True
    applicable_actions: frozenset[ActionType] = Field(
        default_factory=lambda: SERVICE_OPERATIONS
    )

    @model_validator(mode="after")
    def validate_check(self) -> VerificationCheck:
        if self.check_type is VerificationCheckType.HTTP_HEALTH:
            if self.endpoint_ref is None or self.expected_http_status is None:
                raise ValueError("HTTP_HEALTH requires endpoint_ref and expected_http_status")
            if self.expected_service_state is not None:
                raise ValueError("HTTP_HEALTH cannot define expected_service_state")
        elif self.expected_service_state is None:
            raise ValueError("Service/process checks require expected_service_state")
        if not self.applicable_actions or not self.applicable_actions <= SERVICE_OPERATIONS:
            raise ValueError("Verification applicability must use service operations")
        return self


class VerificationProfile(StrictDeploymentModel):
    id: str = Field(pattern=SAFE_REF.pattern)
    checks: tuple[VerificationCheck, ...] = Field(min_length=1, max_length=10)
    retry_interval_seconds: float = Field(default=1.0, ge=0.1, le=60)
    timeout_seconds: int = Field(default=30, ge=1, le=300)

    @model_validator(mode="after")
    def require_success_criteria(self) -> VerificationProfile:
        if not any(check.required for check in self.checks):
            raise ValueError("Verification profile requires at least one required check")
        return self


class LegacyTicketProfile(StrictDeploymentModel):
    id: str = Field(pattern=SAFE_REF.pattern)
    base_url_ref: str = Field(pattern=SAFE_REF.pattern)
    tickets_path: str = Field(default="/tickets", pattern=r"^/[A-Za-z0-9_./-]{1,200}$")
    auth_token_env_ref: str | None = Field(default=None, pattern=SAFE_ENV_REF.pattern)


class ObservabilityProfile(StrictDeploymentModel):
    id: str = Field(pattern=SAFE_REF.pattern)
    health: bool = True
    metrics: bool = False
    logs: bool = False
    tickets: bool = False


class DeploymentConfiguration(StrictDeploymentModel):
    schema_version: Literal["1"]
    inventory_catalog: dict[str, str]
    remote_user_catalog: dict[str, str]
    endpoint_catalog: dict[str, str] = Field(default_factory=dict)
    connections: tuple[AnsibleConnectionProfile, ...] = Field(min_length=1)
    service_controls: tuple[ServiceControlProfile, ...] = Field(min_length=1)
    verifications: tuple[VerificationProfile, ...] = Field(min_length=1)
    tickets: tuple[LegacyTicketProfile, ...] = ()
    observability: tuple[ObservabilityProfile, ...] = ()
    targets: tuple[DeploymentTargetProfile, ...] = Field(min_length=1)
    database_url_env_ref: str | None = Field(default=None, pattern=SAFE_ENV_REF.pattern)
    required_ports: tuple[int, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def validate_catalog(self) -> DeploymentConfiguration:
        collections: tuple[tuple[str, list[str]], ...] = (
            ("connection", [item.id for item in self.connections]),
            ("service control", [item.id for item in self.service_controls]),
            ("verification", [item.id for item in self.verifications]),
            ("ticket", [item.id for item in self.tickets]),
            ("observability", [item.id for item in self.observability]),
        )
        for label, ids in collections:
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {label} profile")
        target_ids = [target.profile_id for target in self.targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("Duplicate deployment target profile")
        identities = [
            (target.environment, target.service, target.target_ref) for target in self.targets
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate semantic deployment target")
        for ref, path in self.inventory_catalog.items():
            if not SAFE_REF.fullmatch(ref) or not SAFE_CONFIG_PATH.fullmatch(path) or ".." in path:
                raise ValueError("Inventory catalog contains an unsafe reference or path")
        for ref, user in self.remote_user_catalog.items():
            if (
                not SAFE_REF.fullmatch(ref)
                or not SAFE_MAPPING.fullmatch(user)
                or user.startswith("-")
            ):
                raise ValueError("Remote user catalog contains an unsafe mapping")
        for ref, endpoint in self.endpoint_catalog.items():
            parsed = urlsplit(endpoint)
            if (
                not SAFE_REF.fullmatch(ref)
                or parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise ValueError("Endpoint catalog requires credential-free HTTP(S) URLs")
        connections = {item.id: item for item in self.connections}
        controls = {item.id: item for item in self.service_controls}
        verifications = {item.id: item for item in self.verifications}
        tickets = {item.id: item for item in self.tickets}
        observability = {item.id: item for item in self.observability}
        for connection in self.connections:
            if connection.inventory_ref not in self.inventory_catalog:
                raise ValueError("Connection references an unknown inventory")
            if connection.remote_user_ref not in self.remote_user_catalog:
                raise ValueError("Connection references an unknown remote user")
        for verification in self.verifications:
            for check in verification.checks:
                if check.endpoint_ref and check.endpoint_ref not in self.endpoint_catalog:
                    raise ValueError("Verification references an unknown endpoint")
        for ticket in self.tickets:
            if ticket.base_url_ref not in self.endpoint_catalog:
                raise ValueError("Ticket profile references an unknown endpoint")
        for target in self.targets:
            if target.connection_profile_ref not in connections:
                raise ValueError("Target references an unknown connection profile")
            control = controls.get(target.service_control_profile_ref)
            if control is None:
                raise ValueError("Target references an unknown service control profile")
            if target.health_profile_ref not in verifications:
                raise ValueError("Target references an unknown verification profile")
            if target.ticket_profile_ref and target.ticket_profile_ref not in tickets:
                raise ValueError("Target references an unknown ticket profile")
            if (
                target.observability_profile_ref
                and target.observability_profile_ref not in observability
            ):
                raise ValueError("Target references an unknown observability profile")
            if target.service not in control.service_mapping:
                raise ValueError("Target service is missing from its service mapping")
            if (
                not target.allowed_actions
                or not target.allowed_actions <= control.allowed_operations
            ):
                raise ValueError("Target actions exceed its service control allowlist")
            verification = verifications[target.health_profile_ref]
            uncovered = {
                action
                for action in target.allowed_actions
                if not any(
                    check.required and action in check.applicable_actions
                    for check in verification.checks
                )
            }
            if uncovered:
                raise ValueError("Target action has no required verification check")
        return self


class DeploymentPreview(StrictDeploymentModel):
    semantic_action: ActionType
    service: str
    environment: str
    target_ref: str
    execution_backend: Literal["Ansible"] = "Ansible"
    control_type: ServiceControlType
    verification: tuple[VerificationCheckType, ...]
    approval_required: bool


class AssessmentItem(StrictDeploymentModel):
    capability: str
    status: Literal["READY", "MISSING", "OPTIONAL"]


class MigrationAssessment(StrictDeploymentModel):
    profile_id: str
    items: tuple[AssessmentItem, ...]
    readiness_levels: frozenset[ReadinessLevel]
    result: str
