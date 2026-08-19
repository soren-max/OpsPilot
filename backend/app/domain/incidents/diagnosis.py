from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class HypothesisStatus(StrEnum):
    PROPOSED = "PROPOSED"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    CONFIRMED = "CONFIRMED"


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    incident_id: str
    statement: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    status: HypothesisStatus
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    created_at: datetime
    created_by: str = Field(min_length=1, max_length=80)


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    incident_id: str
    root_cause: str = Field(min_length=1, max_length=4000)
    contributing_factors: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    confidence: float = Field(ge=0, le=1)
    created_by: str = Field(min_length=1, max_length=80)
    created_at: datetime
