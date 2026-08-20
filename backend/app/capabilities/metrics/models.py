from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictCapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MetricKind(StrEnum):
    CPU_USAGE = "CPU_USAGE"
    MEMORY_USAGE = "MEMORY_USAGE"
    REQUEST_RATE = "REQUEST_RATE"
    ERROR_RATE = "ERROR_RATE"
    LATENCY_P95 = "LATENCY_P95"
    SERVICE_UP = "SERVICE_UP"


class MetricAggregation(StrEnum):
    AVG = "AVG"
    MAX = "MAX"
    SUM = "SUM"


class MetricQuery(StrictCapabilityModel):
    metric_kind: MetricKind
    service: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    environment: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    start: datetime
    end: datetime
    step_seconds: int = Field(ge=1, le=3600)
    aggregation: MetricAggregation = MetricAggregation.AVG


class MetricPoint(StrictCapabilityModel):
    timestamp: datetime
    value: float


class MetricSeries(StrictCapabilityModel):
    labels: dict[str, str] = Field(default_factory=dict)
    points: tuple[MetricPoint, ...]


class MetricObservation(StrictCapabilityModel):
    query_kind: MetricKind
    service: str
    environment: str
    start: datetime
    end: datetime
    series: tuple[MetricSeries, ...]
    summary: str = Field(min_length=1, max_length=1000)
    source_reference: str = Field(min_length=1, max_length=1000)
    collected_at: datetime
