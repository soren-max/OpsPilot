from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.approvals import ApprovalDecision, ApprovalStatus


class ApprovalDecisionCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ApprovalRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    workflow_run_id: str
    action_request_id: str
    action_fingerprint: str
    status: ApprovalStatus
    requested_at: datetime
    resolved_at: datetime | None
    approver_identity: str | None
    approver_display_name: str | None
    approver_type: str | None
    decision: ApprovalDecision | None
    reason: str | None
    resumed_at: datetime | None
