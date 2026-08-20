from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictCapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class HealthQuery(StrictCapabilityModel):
    service: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    environment: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")


class HealthObservation(StrictCapabilityModel):
    service: str
    environment: str
    status: HealthStatus
    summary: str = Field(min_length=1, max_length=1000)
    source_reference: str = Field(min_length=1, max_length=1000)
    observed_at: datetime
    collected_at: datetime
