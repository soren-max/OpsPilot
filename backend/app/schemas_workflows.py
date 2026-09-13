from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

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

    @field_serializer("state_references")
    def hide_internal_replay_snapshot(self, value: dict[str, object]) -> dict[str, object]:
        """Replay inputs are available only through the governed replay endpoint."""

        return {key: item for key, item in value.items() if key != "replay_snapshot"}


class WorkflowTimelineItem(BaseModel):
    id: str
    event_type: str
    occurred_at: datetime
    summary: str
    node: str | None = None
    duration_ms: int | None = None
    result_status: str | None = None
