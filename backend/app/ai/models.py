from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.actions.models import ActionType
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import JsonValue


class StrictAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InvestigationPromptEvidence(StrictAIModel):
    evidence_id: str = Field(min_length=1, max_length=64)
    evidence_type: EvidenceType
    source: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    summary: str = Field(min_length=1, max_length=500)
    excerpt: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class InvestigationPromptInput(StrictAIModel):
    incident_id: str
    service: str = Field(min_length=1, max_length=120)
    environment: str = Field(min_length=1, max_length=80)
    evidence: tuple[InvestigationPromptEvidence, ...] = Field(max_length=20)
    prompt_name: str
    prompt_version: str


class InvestigationModelOutput(StrictAIModel):
    statement: str = Field(min_length=1, max_length=2000)
    root_cause: str = Field(min_length=1, max_length=4000)
    decision_summary: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: tuple[str, ...] = Field(max_length=20)
    action_type: ActionType | None
    insufficient_evidence: bool
    uncertainty: str | None = Field(max_length=1000)


class ModelUsage(StrictAIModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class StructuredReasoningResult(StrictAIModel):
    output: InvestigationModelOutput
    provider: str
    model: str
    prompt_version: str
    latency_ms: int = Field(ge=0)
    usage: ModelUsage = Field(default_factory=ModelUsage)
