from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictCapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LogSeverity(StrEnum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class LogQuery(StrictCapabilityModel):
    service: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    environment: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    start: datetime
    end: datetime
    severity: LogSeverity | None = None
    keywords: tuple[str, ...] = Field(default=(), max_length=5)
    limit: int = Field(ge=1, le=1000)


class LogEntry(StrictCapabilityModel):
    timestamp: datetime
    level: str = Field(min_length=1, max_length=20)
    message_excerpt: str = Field(max_length=1000)
    labels: dict[str, str] = Field(default_factory=dict)
    source_reference: str = Field(min_length=1, max_length=1000)


class LogObservation(StrictCapabilityModel):
    service: str
    environment: str
    start: datetime
    end: datetime
    entries: tuple[LogEntry, ...]
    summary: str = Field(min_length=1, max_length=1000)
    source_reference: str = Field(min_length=1, max_length=1000)
    collected_at: datetime
