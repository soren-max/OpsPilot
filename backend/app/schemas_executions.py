from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.execution import BackendType, ExecutionStatus


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    incident_id: str
    workflow_id: str
    action_fingerprint: str
    backend_type: BackendType
    backend_profile: str
    status: ExecutionStatus
    provider_execution_id: str | None
    attempt: int
    submitted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    last_reconciled_at: datetime | None
    failure_category: str | None
    safe_failure_message: str | None
    trace_id: str | None
    version: int
    safe_provider_status: str | None
    verification_status: str | None
    artifact_digest: str | None
    git_commit_sha: str | None
    created_at: datetime
