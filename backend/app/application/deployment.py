from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain.actions.models import ActionType, TargetEnvironment


class DeploymentTargetProfile(BaseModel):
    """Semantic deployment target resolved before infrastructure dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    profile_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
    environment: TargetEnvironment
    service: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
    target_ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
    connection_profile_ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
    service_control_profile_ref: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$"
    )
    health_profile_ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
    ticket_profile_ref: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$"
    )
    observability_profile_ref: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$"
    )
    allowed_actions: frozenset[ActionType]


class DeploymentEnvironmentResolver(Protocol):
    """Application port: semantic identity to an approved operator-owned profile."""

    def resolve(
        self,
        *,
        service: str,
        environment: TargetEnvironment,
        target_ref: str,
    ) -> DeploymentTargetProfile: ...
