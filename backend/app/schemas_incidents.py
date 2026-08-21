from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.audit.models import ActorType, AuditEventType
from app.domain.incidents.diagnosis import HypothesisStatus
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.knowledge import IncidentKnowledgeRecord
from app.domain.incidents.models import IncidentStatus, JsonValue, Severity


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=4000)
    severity: Severity
    environment: str = Field(min_length=1, max_length=80)
    service: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        tags = sorted({tag.strip().lower() for tag in value if tag.strip()})
        if any(len(tag) > 64 for tag in tags):
            raise ValueError("tags may not exceed 64 characters")
        return tags


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_type: EvidenceType
    source: str = Field(min_length=1, max_length=120)
    source_reference: str = Field(min_length=1, max_length=1000)
    summary: str = Field(min_length=1, max_length=1000)
    excerpt: str | None = Field(default=None, max_length=8000)
    observed_at: datetime
    collector: str = Field(min_length=1, max_length=120)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class HypothesisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    supporting_evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    contradicting_evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class DiagnosisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root_cause: str = Field(min_length=1, max_length=4000)
    contributing_factors: list[str] = Field(default_factory=list, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    confidence: float = Field(ge=0, le=1)


class VersionedMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class EvidenceRead(EvidenceCreate):
    id: str
    incident_id: str
    collected_at: datetime
    fingerprint: str


class HypothesisRead(HypothesisCreate):
    id: str
    incident_id: str
    created_at: datetime
    created_by: str


class DiagnosisRead(DiagnosisCreate):
    id: str
    incident_id: str
    created_at: datetime
    created_by: str


class IncidentActionRead(BaseModel):
    task_id: str
    action_fingerprint: str
    created_at: datetime


class IncidentRead(IncidentCreate):
    id: str
    status: IncidentStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    version: int
    evidence: list[EvidenceRead] = Field(default_factory=list)
    hypotheses: list[HypothesisRead] = Field(default_factory=list)
    diagnoses: list[DiagnosisRead] = Field(default_factory=list)
    actions: list[IncidentActionRead] = Field(default_factory=list)


class IncidentPage(BaseModel):
    items: list[IncidentRead]
    offset: int
    limit: int
    count: int


class TimelineKind(StrEnum):
    INCIDENT = "INCIDENT"
    EVIDENCE = "EVIDENCE"
    HYPOTHESIS = "HYPOTHESIS"
    DIAGNOSIS = "DIAGNOSIS"
    ACTION = "ACTION"
    APPROVAL = "APPROVAL"
    VERIFICATION = "VERIFICATION"
    WORKFLOW = "WORKFLOW"


class TimelineItem(BaseModel):
    id: str
    kind: TimelineKind
    event_type: str
    occurred_at: datetime
    summary: str
    reference_id: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class AuditEventRead(BaseModel):
    event_id: str
    incident_id: str
    event_type: AuditEventType
    actor_type: ActorType
    actor_id: str
    correlation_id: str
    causation_id: str | None
    occurred_at: datetime
    payload_summary: str
    metadata: dict[str, JsonValue]


class KnowledgeRecordRead(IncidentKnowledgeRecord):
    pass


class RetrievedKnowledgeRead(BaseModel):
    knowledge_id: str
    incident_id: str
    title: str
    service: str
    environment: str
    root_cause: str
    remediation: tuple[str, ...]
    verification: tuple[str, ...]
    retrieval_score: float
    source_reference: str
    resolved_at: datetime
