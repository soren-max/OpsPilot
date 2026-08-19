from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AuditEventType(StrEnum):
    ACTION_PROPOSED = "action_proposed"
    RISK_ASSESSED = "risk_assessed"
    APPROVAL_REQUESTED = "approval_requested"
    ACTION_EXECUTED = "action_executed"
    ACTION_VERIFIED = "action_verified"


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    incident_id: str
    event_type: AuditEventType
    actor: str
    summary: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
