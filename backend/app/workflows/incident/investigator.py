from dataclasses import dataclass
from typing import Protocol

from app.domain.actions.models import ActionType
from app.domain.incidents.evidence import EvidenceType


@dataclass(frozen=True)
class InvestigationEvidence:
    evidence_id: str
    evidence_type: EvidenceType
    summary: str
    excerpt: str | None


@dataclass(frozen=True)
class InvestigationContext:
    incident_id: str
    service: str
    environment: str
    evidence: tuple[InvestigationEvidence, ...]
    retrieved_knowledge_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class InvestigationResult:
    statement: str
    root_cause: str
    decision_summary: str
    confidence: float
    evidence_ids: tuple[str, ...]
    action_type: ActionType | None


class IncidentInvestigator(Protocol):
    def investigate(self, context: InvestigationContext) -> InvestigationResult: ...


class DeterministicInvestigator:
    """M2 fixture implementation; no model call or hidden reasoning is involved."""

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
            )
        return InvestigationResult(
            statement="No remediation signal is present in the available evidence.",
            root_cause="No actionable service failure identified",
            decision_summary="Available evidence does not justify a mutating action.",
            confidence=0.7,
            evidence_ids=tuple(item.evidence_id for item in context.evidence),
            action_type=None,
        )
