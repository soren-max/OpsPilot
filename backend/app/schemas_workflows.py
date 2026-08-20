from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.repositories.workflow_models import WorkflowRunStatus


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    graph_name: str
    graph_version: str
    status: WorkflowRunStatus
    started_by: str
    current_node: str | None
    started_at: datetime | None
    finished_at: datetime | None
    last_checkpoint_at: datetime | None
    last_error: str | None
    state_references: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class WorkflowTimelineItem(BaseModel):
    id: str
    event_type: str
    occurred_at: datetime
    summary: str
    node: str | None = None
    duration_ms: int | None = None
    result_status: str | None = None
