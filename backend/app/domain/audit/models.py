from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.incidents.models import JsonValue


class ActorType(StrEnum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    TOOL = "TOOL"


class AuditEventType(StrEnum):
    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_STATE_CHANGED = "INCIDENT_STATE_CHANGED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    HYPOTHESIS_ADDED = "HYPOTHESIS_ADDED"
    HYPOTHESIS_UPDATED = "HYPOTHESIS_UPDATED"
    DIAGNOSIS_RECORDED = "DIAGNOSIS_RECORDED"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    RISK_ASSESSED = "RISK_ASSESSED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_APPROVED = "APPROVAL_APPROVED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    ACTION_FAILED = "ACTION_FAILED"
    VERIFICATION_RECORDED = "VERIFICATION_RECORDED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    INCIDENT_CLOSED = "INCIDENT_CLOSED"
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_NODE_STARTED = "WORKFLOW_NODE_STARTED"
    WORKFLOW_NODE_COMPLETED = "WORKFLOW_NODE_COMPLETED"
    WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
    WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    LLM_INVESTIGATION_STARTED = "LLM_INVESTIGATION_STARTED"
    LLM_INVESTIGATION_COMPLETED = "LLM_INVESTIGATION_COMPLETED"
    LLM_INVESTIGATION_FAILED = "LLM_INVESTIGATION_FAILED"


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str
    incident_id: str
    event_type: AuditEventType
    actor_type: ActorType
    actor_id: str = Field(min_length=1, max_length=80)
    correlation_id: str
    causation_id: str | None = None
    occurred_at: datetime
    payload_summary: str = Field(min_length=1, max_length=1000)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
