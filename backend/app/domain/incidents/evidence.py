from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.incidents.models import JsonValue


class EvidenceType(StrEnum):
    ALERT = "ALERT"
    METRIC = "METRIC"
    LOG = "LOG"
    TICKET = "TICKET"
    SERVICE_STATUS = "SERVICE_STATUS"
    OPERATOR_NOTE = "OPERATOR_NOTE"
    TOOL_RESULT = "TOOL_RESULT"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    incident_id: str
    evidence_type: EvidenceType
    source: str = Field(min_length=1, max_length=120)
    source_reference: str = Field(min_length=1, max_length=1000)
    summary: str = Field(min_length=1, max_length=1000)
    excerpt: str | None = Field(default=None, max_length=8000)
    observed_at: datetime
    collected_at: datetime
    collector: str = Field(min_length=1, max_length=120)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    fingerprint: str = Field(min_length=64, max_length=64)
