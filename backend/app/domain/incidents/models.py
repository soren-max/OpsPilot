from pydantic import BaseModel, ConfigDict, Field


class IncidentSummary(BaseModel):
    """Minimal boundary for Milestone 1A; workflow behavior is planned for M2."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    incident_id: str = Field(min_length=1, max_length=64)
    user_query: str = Field(min_length=1, max_length=2000)
    decision_summary: str | None = None
