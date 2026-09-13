from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.audit.models import AuditEventType
from app.repositories.incident_models import IncidentAuditEventRecord
from app.repositories.incidents import AuditEventRepository, IncidentRepository
from app.repositories.workflow_models import WorkflowRunRecord
from app.repositories.workflows import WorkflowRunRepository
from app.schemas_incidents import AgentEvent, AgentStage


@dataclass(frozen=True)
class EventPresentation:
    event_type: str
    stage: AgentStage
    default_status: str


EVENT_PRESENTATION: dict[AuditEventType, EventPresentation] = {
    AuditEventType.INCIDENT_CREATED: EventPresentation(
        "incident.created", AgentStage.ALERT, "RECEIVED"
    ),
    AuditEventType.INCIDENT_STATE_CHANGED: EventPresentation(
        "incident.state_changed", AgentStage.INCIDENT, "UPDATED"
    ),
    AuditEventType.INCIDENT_RESOLVED: EventPresentation(
        "incident.resolved", AgentStage.INCIDENT, "RESOLVED"
    ),
    AuditEventType.INCIDENT_CLOSED: EventPresentation(
        "incident.closed", AgentStage.INCIDENT, "CLOSED"
    ),
    AuditEventType.EVIDENCE_ADDED: EventPresentation(
        "evidence.collected", AgentStage.EVIDENCE, "SUCCEEDED"
    ),
    AuditEventType.HYPOTHESIS_ADDED: EventPresentation(
        "diagnosis.hypothesis_created", AgentStage.DIAGNOSIS, "SUCCEEDED"
    ),
    AuditEventType.HYPOTHESIS_UPDATED: EventPresentation(
        "diagnosis.hypothesis_updated", AgentStage.DIAGNOSIS, "UPDATED"
    ),
    AuditEventType.DIAGNOSIS_RECORDED: EventPresentation(
        "diagnosis.created", AgentStage.DIAGNOSIS, "SUCCEEDED"
    ),
    AuditEventType.ACTION_PROPOSED: EventPresentation(
        "proposal.created", AgentStage.PROPOSAL, "SUCCEEDED"
    ),
    AuditEventType.RISK_ASSESSED: EventPresentation(
        "policy.evaluated", AgentStage.POLICY, "EVALUATED"
    ),
    AuditEventType.APPROVAL_REQUESTED: EventPresentation(
        "approval.requested", AgentStage.APPROVAL, "WAITING"
    ),
    AuditEventType.APPROVAL_GRANTED: EventPresentation(
        "approval.approved", AgentStage.APPROVAL, "APPROVED"
    ),
    AuditEventType.APPROVAL_APPROVED: EventPresentation(
        "approval.approved", AgentStage.APPROVAL, "APPROVED"
    ),
    AuditEventType.APPROVAL_REJECTED: EventPresentation(
        "approval.rejected", AgentStage.APPROVAL, "REJECTED"
    ),
    AuditEventType.EXECUTION_ROUTED: EventPresentation(
        "execution.routed", AgentStage.EXECUTION, "ROUTED"
    ),
    AuditEventType.EXECUTION_QUEUED: EventPresentation(
        "execution.queued", AgentStage.EXECUTION, "QUEUED"
    ),
    AuditEventType.EXECUTION_DISPATCHED: EventPresentation(
        "execution.dispatched", AgentStage.EXECUTION, "DISPATCHED"
    ),
    AuditEventType.EXECUTION_SUBMITTED: EventPresentation(
        "execution.submitted", AgentStage.EXECUTION, "SUBMITTED"
    ),
    AuditEventType.EXECUTION_UNKNOWN: EventPresentation(
        "execution.unknown", AgentStage.EXECUTION, "UNKNOWN"
    ),
    AuditEventType.EXECUTION_SUCCEEDED: EventPresentation(
        "execution.succeeded", AgentStage.EXECUTION, "SUCCEEDED"
    ),
    AuditEventType.EXECUTION_FAILED: EventPresentation(
        "execution.failed", AgentStage.EXECUTION, "FAILED"
    ),
    AuditEventType.EXECUTION_RECONCILED: EventPresentation(
        "reconciliation.resolved", AgentStage.RECONCILIATION, "RECONCILED"
    ),
    AuditEventType.EXECUTION_VERIFICATION_FAILED: EventPresentation(
        "verification.failed", AgentStage.VERIFICATION, "FAILED"
    ),
    AuditEventType.VERIFICATION_RECORDED: EventPresentation(
        "verification.completed", AgentStage.VERIFICATION, "COMPLETED"
    ),
    AuditEventType.WORKFLOW_STARTED: EventPresentation(
        "workflow.started", AgentStage.WORKFLOW, "RUNNING"
    ),
    AuditEventType.WORKFLOW_PAUSED: EventPresentation(
        "approval.waiting", AgentStage.APPROVAL, "WAITING"
    ),
    AuditEventType.WORKFLOW_RESUMED: EventPresentation(
        "workflow.resumed", AgentStage.WORKFLOW, "RUNNING"
    ),
    AuditEventType.WORKFLOW_FAILED: EventPresentation(
        "workflow.failed", AgentStage.WORKFLOW, "FAILED"
    ),
    AuditEventType.WORKFLOW_COMPLETED: EventPresentation(
        "workflow.completed", AgentStage.WORKFLOW, "SUCCEEDED"
    ),
    AuditEventType.LLM_INVESTIGATION_STARTED: EventPresentation(
        "diagnosis.started", AgentStage.DIAGNOSIS, "RUNNING"
    ),
    AuditEventType.LLM_INVESTIGATION_COMPLETED: EventPresentation(
        "grounding.validated", AgentStage.GROUNDING, "SUCCEEDED"
    ),
    AuditEventType.LLM_INVESTIGATION_FAILED: EventPresentation(
        "grounding.rejected", AgentStage.GROUNDING, "FAILED"
    ),
}

NODE_PRESENTATION: dict[tuple[str, str], EventPresentation] = {
    ("collect_context", "started"): EventPresentation(
        "evidence.started", AgentStage.EVIDENCE, "RUNNING"
    ),
    ("collect_context", "completed"): EventPresentation(
        "evidence.collected", AgentStage.EVIDENCE, "SUCCEEDED"
    ),
    ("retrieve_knowledge", "started"): EventPresentation(
        "memory.retrieval_started", AgentStage.MEMORY, "RUNNING"
    ),
    ("retrieve_knowledge", "completed"): EventPresentation(
        "memory.retrieved", AgentStage.MEMORY, "SUCCEEDED"
    ),
    ("investigate", "started"): EventPresentation(
        "diagnosis.started", AgentStage.DIAGNOSIS, "RUNNING"
    ),
    ("investigate", "completed"): EventPresentation(
        "grounding.validated", AgentStage.GROUNDING, "SUCCEEDED"
    ),
    ("diagnose", "completed"): EventPresentation(
        "diagnosis.created", AgentStage.DIAGNOSIS, "SUCCEEDED"
    ),
    ("propose_action", "completed"): EventPresentation(
        "proposal.created", AgentStage.PROPOSAL, "SUCCEEDED"
    ),
    ("assess_risk", "completed"): EventPresentation(
        "policy.evaluated", AgentStage.POLICY, "EVALUATED"
    ),
    ("approval_required", "started"): EventPresentation(
        "approval.requested", AgentStage.APPROVAL, "WAITING"
    ),
    ("execute", "started"): EventPresentation(
        "execution.dispatch_started", AgentStage.EXECUTION, "RUNNING"
    ),
    ("verify", "started"): EventPresentation(
        "verification.started", AgentStage.VERIFICATION, "RUNNING"
    ),
    ("verify", "completed"): EventPresentation(
        "verification.completed", AgentStage.VERIFICATION, "COMPLETED"
    ),
}


class AgentEventProjection:
    """Projects durable audit rows into the UI event contract without creating new truth."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.incidents = IncidentRepository(db)
        self.audits = AuditEventRepository(db)
        self.workflows = WorkflowRunRepository(db)

    def list(
        self, incident_id: str, *, after_event_id: str | None = None, limit: int = 200
    ) -> list[AgentEvent]:
        if self.incidents.get(incident_id) is None:
            from app.core.errors import NotFoundError

            raise NotFoundError("Incident does not exist")
        rows = self.audits.list_for_incident_after(
            incident_id, after_event_id=after_event_id, limit=limit
        )
        workflow_cache: dict[str, WorkflowRunRecord | None] = {}
        return [self._project(row, workflow_cache) for row in rows]

    def _project(
        self,
        row: IncidentAuditEventRecord,
        workflow_cache: dict[str, WorkflowRunRecord | None],
    ) -> AgentEvent:
        presentation = self._presentation(row)
        data = dict(row.event_metadata)
        data["summary"] = row.payload_summary
        data["actor_type"] = row.actor_type.value
        data["actor_id"] = row.actor_id
        if row.correlation_id not in workflow_cache:
            workflow_cache[row.correlation_id] = self.workflows.get(row.correlation_id)
        workflow = workflow_cache[row.correlation_id]
        if workflow is not None:
            for key in (
                "investigator_mode",
                "provider",
                "model",
                "prompt_version",
                "action_type",
                "risk_level",
                "policy_decision",
                "policy_rule",
                "policy_reason",
                "expected_result",
            ):
                value = workflow.state_references.get(key)
                if isinstance(value, (str, int, float, bool)) or value is None:
                    data.setdefault(key, value)
            if presentation.stage is AgentStage.MEMORY:
                snapshot = workflow.state_references.get("replay_snapshot")
                if isinstance(snapshot, dict):
                    refs = snapshot.get("historical_knowledge", [])
                    if isinstance(refs, list):
                        data["historical_incident_ids"] = [
                            item.get("incident_id")
                            for item in refs[:10]
                            if isinstance(item, dict) and isinstance(item.get("incident_id"), str)
                        ]
        status = data.get("result_status")
        return AgentEvent(
            event_id=row.event_id,
            incident_id=row.incident_id,
            event_type=presentation.event_type,
            stage=presentation.stage,
            timestamp=row.occurred_at,
            status=status if isinstance(status, str) else presentation.default_status,
            data=data,
        )

    @staticmethod
    def _presentation(row: IncidentAuditEventRecord) -> EventPresentation:
        node = row.event_metadata.get("node")
        if isinstance(node, str) and row.event_type in {
            AuditEventType.WORKFLOW_NODE_STARTED,
            AuditEventType.WORKFLOW_NODE_COMPLETED,
        }:
            phase = (
                "started" if row.event_type is AuditEventType.WORKFLOW_NODE_STARTED else "completed"
            )
            if presentation := NODE_PRESENTATION.get((node, phase)):
                return presentation
        return EVENT_PRESENTATION.get(
            row.event_type,
            EventPresentation(
                row.event_type.value.lower().replace("_", "."),
                AgentStage.WORKFLOW,
                "RECORDED",
            ),
        )
