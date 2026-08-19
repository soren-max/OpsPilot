from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import JsonValue as PydanticJsonValue

JsonValue = PydanticJsonValue


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    severity: Severity
    status: IncidentStatus
    environment: str = Field(min_length=1, max_length=80)
    service: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=120)
    created_by: str = Field(min_length=1, max_length=80)
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    tags: tuple[str, ...] = ()
    version: int = Field(ge=1)

    @field_validator("tags")
    @classmethod
    def tags_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({tag.strip().lower() for tag in value if tag.strip()}))
        if len(normalized) > 50 or any(len(tag) > 64 for tag in normalized):
            raise ValueError("tags must contain at most 50 values of 64 characters")
        return normalized


IncidentSummary = Incident
