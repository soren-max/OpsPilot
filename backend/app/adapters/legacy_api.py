from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class LegacyRestartRequest(BaseModel):
    """Temporary safe subset of a synthetic legacy business API."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    incident_id: str = Field(min_length=1, max_length=64)
    action: Literal["restart"]
    service: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
    reason: str = Field(min_length=3, max_length=1000)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=20)


class LegacyCompatibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["approval_required", "migration_required"]
    risk_level: str | None = None
    approval_required: bool
    approval_id: str | None = None
    workflow_id: str | None = None


class GovernedRemediationProposer(Protocol):
    async def propose_restart(
        self, request: LegacyRestartRequest, *, actor: str
    ) -> LegacyCompatibilityResult: ...
