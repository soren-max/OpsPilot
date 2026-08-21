from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.actions.models import ActionType
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.memory import RetrievedKnowledge
from app.domain.incidents.models import JsonValue


@dataclass(frozen=True)
class InvestigationEvidence:
    evidence_id: str
    evidence_type: EvidenceType
    source: str
    observed_at: datetime
    summary: str
    excerpt: str | None
    metadata: dict[str, JsonValue]


@dataclass(frozen=True)
class InvestigatorMetadata:
    mode: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True)
class InvestigationContext:
    incident_id: str
    service: str
    environment: str
    evidence: tuple[InvestigationEvidence, ...]
    retrieved_knowledge_refs: tuple[str, ...] = ()
    historical_knowledge: tuple[RetrievedKnowledge, ...] = ()


@dataclass(frozen=True)
class InvestigationResult:
    statement: str
    root_cause: str
    decision_summary: str
    confidence: float
    evidence_ids: tuple[str, ...]
    action_type: ActionType | None
    knowledge_refs: tuple[str, ...] = ()
    insufficient_evidence: bool = False
    uncertainty: str | None = None
    investigator_mode: str = "deterministic"
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class IncidentInvestigator(Protocol):
    mode: str

    @property
    def metadata(self) -> InvestigatorMetadata: ...

    def investigate(self, context: InvestigationContext) -> InvestigationResult: ...


class DeterministicInvestigator:
    """M2 fixture implementation; no model call or hidden reasoning is involved."""

    mode = "deterministic"

    @property
    def metadata(self) -> InvestigatorMetadata:
        return InvestigatorMetadata(mode=self.mode)

    def investigate(self, context: InvestigationContext) -> InvestigationResult:
        unavailable = [
            item
            for item in context.evidence
            if item.evidence_type is EvidenceType.SERVICE_STATUS
            and "unavailable" in f"{item.summary} {item.excerpt or ''}".lower()
        ]
        if unavailable:
            return InvestigationResult(
                statement="The service process is unavailable.",
                root_cause="Service process unavailable",
                decision_summary=(
                    "Service-status evidence deterministically indicates unavailability."
                ),
                confidence=0.95,
                evidence_ids=tuple(item.evidence_id for item in unavailable),
                action_type=ActionType.RESTART_SERVICE,
                knowledge_refs=context.retrieved_knowledge_refs,
            )
        read_only = [
            item
            for item in context.evidence
            if "read-only-check" in f"{item.summary} {item.excerpt or ''}".lower()
        ]
        if read_only:
            return InvestigationResult(
                statement="Service health should be checked without mutation.",
                root_cause="Health requires verification",
                decision_summary="Evidence requests a deterministic read-only status check.",
                confidence=0.8,
                evidence_ids=tuple(item.evidence_id for item in read_only),
                action_type=ActionType.GET_SERVICE_STATUS,
                knowledge_refs=context.retrieved_knowledge_refs,
            )
        return InvestigationResult(
            statement="No remediation signal is present in the available evidence.",
            root_cause="No actionable service failure identified",
            decision_summary="Available evidence does not justify a mutating action.",
            confidence=0.7,
            evidence_ids=tuple(item.evidence_id for item in context.evidence),
            action_type=None,
            knowledge_refs=context.retrieved_knowledge_refs,
        )
