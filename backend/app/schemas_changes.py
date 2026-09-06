from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.domain.change import ChangeIntent, ChangePreview, ChangeStatus, ChangeType


class ChangeProposal(ChangeIntent):
    """JSON transport permits enum strings and arrays, retaining strict leaf values."""

    change_type: Annotated[ChangeType, Field(strict=False)]
    evidence_ids: Annotated[
        tuple[Annotated[str, Field(min_length=1, max_length=64)], ...], Field(strict=False)
    ]


class ChangeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reason: str = Field(min_length=3, max_length=500)


class ChangeApproval(ChangeDecision):
    plan_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class ChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service: str
    environment: str
    risk: str
    incident_id: str
    workflow_id: str
    profile_id: str
    change_type: ChangeType
    status: ChangeStatus
    source_revision: str | None
    branch: str | None
    commit_sha: str | None
    pull_request_id: str | None
    pull_request_url: str | None
    merged_revision: str | None
    gitops_application_ref: str
    policy_result_ref: str | None
    approval_id: str | None
    approval_actor: str | None
    approval_reason: str | None
    approval_decided_at: datetime | None
    verification_id: str | None
    verification_status: str | None
    gitops_revision: str | None
    sync_status: str | None
    health_status: str | None
    review_state: str | None
    failure_category: str | None
    safe_failure_message: str | None
    created_at: datetime
    updated_at: datetime
    version: int


class ChangePage(BaseModel):
    items: list[ChangeRead]
    count: int


class ChangePreviewRead(ChangePreview):
    pass
