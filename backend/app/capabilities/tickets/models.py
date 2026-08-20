from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictCapabilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TicketQuery(StrictCapabilityModel):
    service: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    environment: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    status: str | None = Field(default=None, max_length=40)
    keywords: tuple[str, ...] = Field(default=(), max_length=5)
    start: datetime
    end: datetime
    limit: int = Field(ge=1, le=100)


class TicketRecord(StrictCapabilityModel):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    status: str = Field(min_length=1, max_length=40)
    service: str = Field(min_length=1, max_length=120)
    environment: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=1000)
    resolution: str | None = Field(default=None, max_length=1000)
    created_at: datetime
    resolved_at: datetime | None = None
    source_reference: str = Field(min_length=1, max_length=1000)
