from __future__ import annotations

import time
from datetime import datetime

from opentelemetry import trace
from sqlalchemy.orm import Session

from app.ai.evaluation import compare_replay_result
from app.application.incident_service import IncidentService
from app.core.errors import ConflictError, NotFoundError
from app.domain.actions.models import ActionType
from app.domain.actions.policy import ActionPolicyEngine
from app.domain.incidents.memory import RetrievedKnowledge
from app.repositories.incident_models import DiagnosisRecord, IncidentRecord
from app.repositories.workflows import WorkflowRunRepository
from app.schemas_replay import (
    IncidentReplayRead,
    ReplayDiagnosis,
    ReplayMetrics,
    ReplayPolicy,
    ReplayProposal,
    ReplayRequest,
)
from app.workflows.incident.context import build_incident_action_request
from app.workflows.incident.investigator import (
    IncidentInvestigator,
    InvestigationContext,
    InvestigationEvidence,
)

tracer = trace.get_tracer("opspilot.replay")


class IncidentReplayService:
    """Re-run bounded reasoning over frozen inputs without invoking a workflow or executor."""

    def __init__(
        self,
        db: Session,
        investigator: IncidentInvestigator,
    ) -> None:
        self.db = db
        self.investigator = investigator
        self.incidents = IncidentService(db)
        self.workflows = WorkflowRunRepository(db)

    def replay(self, incident_id: str, request: ReplayRequest) -> IncidentReplayRead:
        incident = self.incidents._require(incident_id)
        workflow = (
            self.workflows.get(request.workflow_id)
            if request.workflow_id is not None
            else next(iter(self.workflows.list_for_incident(incident_id)), None)
        )
        if workflow is None or workflow.incident_id != incident_id:
            raise NotFoundError("Workflow does not exist for this incident")
        snapshot = workflow.state_references.get("replay_snapshot")
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "1":
            raise ConflictError(
                "REPLAY_SNAPSHOT_UNAVAILABLE",
                "This workflow predates frozen replay inputs and cannot be replayed safely",
            )
        evidence_ids = self._string_list(snapshot.get("evidence_ids"))
        evidence_by_id = {item.id: item for item in incident.evidence}
        missing = sorted(set(evidence_ids) - set(evidence_by_id))
        if missing:
            raise ConflictError(
                "REPLAY_SNAPSHOT_INCOMPLETE", "Frozen evidence is unavailable", missing
            )
        evidence = tuple(
            InvestigationEvidence(
                evidence_id=item.id,
                evidence_type=item.evidence_type,
                source=item.source,
                observed_at=item.observed_at,
                summary=item.summary,
                excerpt=item.excerpt,
                metadata=item.evidence_metadata,
            )
            for evidence_id in evidence_ids
            for item in (evidence_by_id[evidence_id],)
        )
        history = (
            self._history(snapshot.get("historical_knowledge"))
            if request.with_historical_memory
            else ()
        )
        context = InvestigationContext(
            incident_id=incident.id,
            service=str(snapshot.get("service") or incident.service),
            environment=str(snapshot.get("environment") or incident.environment),
            evidence=evidence,
            retrieved_knowledge_refs=tuple(item.knowledge_id for item in history),
            historical_knowledge=history,
        )
        with tracer.start_as_current_span("incident.replay") as span:
            span.set_attribute("incident.id", incident.id)
            span.set_attribute("workflow.run_id", workflow.id)
            span.set_attribute("workflow.stage", "REPLAY")
            span.set_attribute("evidence.count", len(evidence))
            span.set_attribute("memory.top_k", len(history))
            span.set_attribute("replay.no_side_effect", True)
            started = time.perf_counter()
            result = self.investigator.investigate(context)
            latency_ms = int((time.perf_counter() - started) * 1000)
        original = (
            self.db.get(DiagnosisRecord, workflow.diagnosis_id) if workflow.diagnosis_id else None
        )
        original_action_value = workflow.state_references.get("action_type")
        original_action = (
            ActionType(original_action_value) if isinstance(original_action_value, str) else None
        )
        comparison = compare_replay_result(
            original_root_cause=original.root_cause if original is not None else None,
            original_action=original_action,
            available_evidence_ids=frozenset(evidence_ids),
            replay=result,
        )
        policy = self._policy(incident, workflow.id, result.action_type)
        return IncidentReplayRead(
            incident_id=incident.id,
            workflow_id=workflow.id,
            snapshot_version="1",
            investigator_mode=result.investigator_mode,
            provider=result.provider,
            model=result.model,
            prompt_version=result.prompt_version,
            historical_memory_included=request.with_historical_memory,
            frozen_evidence_ids=evidence_ids,
            frozen_historical_incident_ids=[item.incident_id for item in history],
            original_diagnosis=(
                ReplayDiagnosis(
                    root_cause=original.root_cause,
                    confidence=original.confidence,
                    evidence_ids=list(original.evidence_ids),
                )
                if original is not None
                else None
            ),
            replay_diagnosis=ReplayDiagnosis(
                root_cause=result.root_cause,
                confidence=result.confidence,
                evidence_ids=list(result.evidence_ids),
            ),
            original_proposal=ReplayProposal(
                action_type=original_action.value if original_action else None,
                target=incident.service,
            ),
            replay_proposal=ReplayProposal(
                action_type=result.action_type.value if result.action_type else None,
                target=incident.service,
            ),
            policy=policy,
            metrics=ReplayMetrics(
                root_cause_match=comparison.root_cause_match,
                action_match=comparison.action_match,
                grounding_valid=comparison.grounding_valid,
                latency_ms=result.latency_ms if result.latency_ms is not None else latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost=None,
            ),
        )

    def _policy(
        self, incident: IncidentRecord, workflow_id: str, action_type: ActionType | None
    ) -> ReplayPolicy:
        if action_type is None:
            return ReplayPolicy(
                decision="NO_ACTION",
                risk_level=None,
                policy_rule=None,
                reason="Replay did not propose an action.",
                approval_required=False,
            )
        action = build_incident_action_request(incident, action_type, f"Replay of {workflow_id}")
        # Replay evaluates policy without constructing any execution adapter.
        assessment = ActionPolicyEngine(frozenset({incident.service})).assess(action)
        decision = (
            "HUMAN_APPROVAL_REQUIRED"
            if assessment.approval_required
            else "ALLOWED"
            if assessment.allowed
            else "DENIED"
        )
        return ReplayPolicy(
            decision=decision,
            risk_level=assessment.risk_level.value,
            policy_rule=assessment.policy_rule,
            reason=assessment.reason,
            approval_required=assessment.approval_required,
        )

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ConflictError("REPLAY_SNAPSHOT_INVALID", "Frozen replay input is invalid")
        return value

    @staticmethod
    def _history(value: object) -> tuple[RetrievedKnowledge, ...]:
        if not isinstance(value, list):
            return ()
        result: list[RetrievedKnowledge] = []
        for item in value:
            if not isinstance(item, dict):
                raise ConflictError("REPLAY_SNAPSHOT_INVALID", "Frozen history input is invalid")
            result.append(
                RetrievedKnowledge(
                    knowledge_id=str(item["knowledge_id"]),
                    incident_id=str(item["incident_id"]),
                    title=str(item["title"]),
                    service=str(item["service"]),
                    environment=str(item["environment"]),
                    root_cause=str(item["root_cause"]),
                    remediation=tuple(str(entry) for entry in item.get("remediation", [])),
                    verification=tuple(str(entry) for entry in item.get("verification", [])),
                    retrieval_score=float(item["retrieval_score"]),
                    source_reference=str(item["source_reference"]),
                    resolved_at=datetime.fromisoformat(str(item["resolved_at"])),
                )
            )
        return tuple(result)
