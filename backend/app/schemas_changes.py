from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.change import ChangePreview, ChangeStatus, ChangeType


class ChangeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reason: str = Field(min_length=3, max_length=500)


class ChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
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
