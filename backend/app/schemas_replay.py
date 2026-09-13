from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ReplayInvestigatorMode(StrEnum):
    DETERMINISTIC = "deterministic"
    CONFIGURED = "configured"


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str | None = None
    investigator_mode: ReplayInvestigatorMode = ReplayInvestigatorMode.DETERMINISTIC
    with_historical_memory: bool = True


class ReplayDiagnosis(BaseModel):
    root_cause: str
    confidence: float
    evidence_ids: list[str]


class ReplayProposal(BaseModel):
    action_type: str | None
    target: str


class ReplayPolicy(BaseModel):
    decision: str
    risk_level: str | None
    policy_rule: str | None
    reason: str | None
    approval_required: bool


class ReplayMetrics(BaseModel):
    root_cause_match: bool
    action_match: bool
    grounding_valid: bool
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None


class IncidentReplayRead(BaseModel):
    incident_id: str
    workflow_id: str
    snapshot_version: str
    no_side_effect: bool = True
    investigator_mode: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    historical_memory_included: bool
    frozen_evidence_ids: list[str]
    frozen_historical_incident_ids: list[str]
    original_diagnosis: ReplayDiagnosis | None
    replay_diagnosis: ReplayDiagnosis
    original_proposal: ReplayProposal
    replay_proposal: ReplayProposal
    policy: ReplayPolicy
    metrics: ReplayMetrics
