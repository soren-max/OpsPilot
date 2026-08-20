from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.action_service import ActionService
from app.application.incident_service import IncidentService, safe_audit_metadata
from app.db.base import utc_now
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    RiskAssessment,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.audit.models import ActorType, AuditEventType
from app.domain.incidents.models import IncidentStatus
from app.repositories.incident_models import IncidentAuditEventRecord
from app.repositories.incidents import AuditEventRepository
from app.repositories.workflow_models import WorkflowRunRecord
from app.schemas_incidents import DiagnosisCreate, HypothesisCreate
from app.services.redaction import redact_text
from app.workflows.incident.errors import ExecutionFailure, WorkflowInfrastructureFailure
from app.workflows.incident.investigator import (
    IncidentInvestigator,
    InvestigationContext,
    InvestigationEvidence,
    InvestigationResult,
)


@dataclass(frozen=True)
class IncidentWorkflowContext:
    runtime: IncidentWorkflowRuntime


class IncidentWorkflowRuntime:
    """Application capabilities used by nodes; nodes never query SQLAlchemy directly."""

    def __init__(
        self,
        db: Session,
        workflow: WorkflowRunRecord,
        investigator: IncidentInvestigator,
        action_service: ActionService | None = None,
    ) -> None:
        self.db = db
        self.workflow = workflow
        self.investigator = investigator
        self.incidents = IncidentService(db)
        self.audits = AuditEventRepository(db)
        self._action_service = action_service
        self._node_started_at: dict[str, float] = {}

    def load_incident(self) -> tuple[int, list[str]]:
        incident = self.incidents._require(self.workflow.incident_id)
        if incident.status is IncidentStatus.OPEN:
            incident = self.incidents.transition(
                incident.id,
                IncidentStatus.INVESTIGATING,
                incident.version,
                "workflow",
                self.workflow.id,
            )
        if incident.status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
            raise ValueError("Resolved or closed incidents cannot start remediation workflows")
        return incident.version, [item.id for item in incident.evidence]

    def investigation_context(self, retrieved_refs: list[str]) -> InvestigationContext:
        incident = self.incidents._require(self.workflow.incident_id)
        return InvestigationContext(
            incident_id=incident.id,
            service=incident.service,
            environment=incident.environment,
            evidence=tuple(
                InvestigationEvidence(
                    evidence_id=item.id,
                    evidence_type=item.evidence_type,
                    summary=item.summary,
                    excerpt=item.excerpt,
                )
                for item in incident.evidence
            ),
            retrieved_knowledge_refs=tuple(retrieved_refs),
        )

    def investigate(self, retrieved_refs: list[str]) -> InvestigationResult:
        return self.investigator.investigate(self.investigation_context(retrieved_refs))

    def record_hypothesis(self, result: InvestigationResult) -> str:
        if self.workflow.hypothesis_id:
            return self.workflow.hypothesis_id
        recovered = self._existing_reference(AuditEventType.HYPOTHESIS_ADDED, "hypothesis_id")
        if recovered is not None:
            self.workflow.hypothesis_id = recovered
            self.db.commit()
            return recovered
        item = self.incidents.add_hypothesis(
            self.workflow.incident_id,
            HypothesisCreate(
                statement=result.statement,
                confidence=result.confidence,
                supporting_evidence_ids=list(result.evidence_ids),
            ),
            "workflow",
            self.workflow.id,
        )
        self.workflow.hypothesis_id = item.id
        self.db.commit()
        return item.id

    def record_diagnosis(self, result: InvestigationResult) -> str:
        if self.workflow.diagnosis_id:
            return self.workflow.diagnosis_id
        recovered = self._existing_reference(AuditEventType.DIAGNOSIS_RECORDED, "diagnosis_id")
        if recovered is not None:
            self.workflow.diagnosis_id = recovered
            self.db.commit()
            return recovered
        item = self.incidents.record_diagnosis(
            self.workflow.incident_id,
            DiagnosisCreate(
                root_cause=result.root_cause,
                evidence_ids=list(result.evidence_ids),
                confidence=result.confidence,
            ),
            "workflow",
            self.workflow.id,
        )
        self.workflow.diagnosis_id = item.id
        self.db.commit()
        return item.id

    def propose_action(self, action_type: ActionType) -> str:
        if self.workflow.proposed_action_id:
            return self.workflow.proposed_action_id
        fingerprint = hashlib.sha256(
            f"{self.workflow.id}:{action_type.value}".encode()
        ).hexdigest()
        self.workflow.proposed_action_id = fingerprint
        self._audit(
            AuditEventType.ACTION_PROPOSED,
            "Workflow proposed a structured action",
            {"workflow_id": self.workflow.id, "action_fingerprint": fingerprint},
        )
        self.db.commit()
        return fingerprint

    def assess_risk(self, action_type: ActionType) -> RiskAssessment:
        action = self._action_request(action_type)
        return self._service().policy.assess(action)

    def execute(self, action_type: ActionType) -> tuple[str, str]:
        if self.workflow.execution_task_id:
            status = self.workflow.state_references.get("verification_status")
            if status in {"SUCCEEDED", "FAILED"}:
                return self.workflow.execution_task_id, str(status)
            raise WorkflowInfrastructureFailure(
                "Action execution state is indeterminate; manual reconciliation is required"
            )
        action = self._action_request(action_type)
        action_fingerprint = self.workflow.proposed_action_id
        if action_fingerprint is None:
            raise WorkflowInfrastructureFailure("Action fingerprint is missing")
        self.workflow.execution_task_id = action_fingerprint
        self.workflow.state_references = {
            "workflow_id": self.workflow.id,
            "action_fingerprint": action_fingerprint,
            "execution_task_id": action_fingerprint,
            "execution_status": "STARTED",
        }
        self.db.commit()
        try:
            outcome = asyncio.run(self._service().execute(action))
        except (ConnectionError, TimeoutError) as exc:
            raise WorkflowInfrastructureFailure(
                "Action capability is temporarily unavailable"
            ) from exc
        except Exception as exc:
            raise ExecutionFailure("Action execution failed") from exc
        if outcome.result is None:
            raise ExecutionFailure(outcome.assessment.reason)
        execution_id = action_fingerprint
        verification = outcome.verification
        status = "SUCCEEDED" if verification is not None and verification.verified else "FAILED"
        self.workflow.execution_task_id = execution_id
        self.workflow.state_references = {
            "workflow_id": self.workflow.id,
            "action_fingerprint": action_fingerprint,
            "execution_task_id": execution_id,
            "execution_status": "COMPLETED",
            "verification_status": status,
        }
        self.db.commit()
        return execution_id, status

    def finalize(self, incident_version: int, *, successful: bool) -> int:
        incident = self.incidents._require(self.workflow.incident_id)
        if successful and incident.status is not IncidentStatus.RESOLVED:
            incident = self.incidents.resolve(
                incident.id, incident_version, "workflow", self.workflow.id
            )
        elif not successful and incident.status not in {
            IncidentStatus.FAILED,
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
        }:
            incident = self.incidents.transition(
                incident.id, IncidentStatus.FAILED, incident_version, "workflow", self.workflow.id
            )
        return incident.version

    def node_started(self, node: str) -> None:
        self._node_started_at[node] = time.monotonic()
        self.workflow.current_node = node
        self.workflow.last_checkpoint_at = utc_now()
        self._audit_once(
            AuditEventType.WORKFLOW_NODE_STARTED,
            f"Workflow node {node} started",
            {"workflow_id": self.workflow.id, "node": node, "result_status": "RUNNING"},
        )
        self.db.commit()

    def node_completed(self, node: str, result_status: str) -> None:
        started = self._node_started_at.pop(node, time.monotonic())
        duration_ms = int((time.monotonic() - started) * 1000)
        self.workflow.last_checkpoint_at = utc_now()
        self._audit_once(
            AuditEventType.WORKFLOW_NODE_COMPLETED,
            f"Workflow node {node} completed",
            {
                "workflow_id": self.workflow.id,
                "node": node,
                "duration_ms": duration_ms,
                "result_status": result_status,
            },
        )
        self.db.commit()

    def audit_workflow(self, event_type: AuditEventType, summary: str, status: str) -> None:
        self._audit_once(
            event_type,
            summary,
            {"workflow_id": self.workflow.id, "result_status": status},
        )
        self.db.commit()

    def _service(self) -> ActionService:
        if self._action_service is None:
            raise WorkflowInfrastructureFailure(
                "Workflow execution requires an operator-configured ActionService"
            )
        return self._action_service

    def _action_request(self, action_type: ActionType) -> ActionRequest:
        incident = self.incidents._require(self.workflow.incident_id)
        environment = {
            "production": TargetEnvironment.PRODUCTION,
            "prod": TargetEnvironment.PRODUCTION,
            "test": TargetEnvironment.TEST,
            "test-mock": TargetEnvironment.TEST,
        }.get(incident.environment.lower(), TargetEnvironment.DEVELOPMENT)
        return ActionRequest(
            action_type=action_type,
            target=incident.service,
            environment=environment,
            parameters=ServiceActionParams(service=incident.service),
            reason=f"Incident workflow {self.workflow.id}",
        )

    def _audit(self, event_type: AuditEventType, summary: str, metadata: dict[str, object]) -> None:
        self.audits.append(
            IncidentAuditEventRecord(
                incident_id=self.workflow.incident_id,
                event_type=event_type,
                actor_type=ActorType.SYSTEM,
                actor_id="workflow",
                correlation_id=self.workflow.id,
                occurred_at=utc_now(),
                payload_summary=redact_text(summary) or "Workflow event",
                event_metadata=safe_audit_metadata(metadata),  # type: ignore[arg-type]
            )
        )

    def _audit_once(
        self, event_type: AuditEventType, summary: str, metadata: dict[str, object]
    ) -> None:
        existing = self.db.scalars(
            select(IncidentAuditEventRecord).where(
                IncidentAuditEventRecord.incident_id == self.workflow.incident_id,
                IncidentAuditEventRecord.correlation_id == self.workflow.id,
                IncidentAuditEventRecord.event_type == event_type,
            )
        )
        safe_metadata = safe_audit_metadata(metadata)  # type: ignore[arg-type]
        identity = {
            key: value
            for key, value in safe_metadata.items()
            if key in {"workflow_id", "node", "result_status"}
        }
        if any(
            all(item.event_metadata.get(key) == value for key, value in identity.items())
            for item in existing
        ):
            return
        self._audit(event_type, summary, metadata)

    def _existing_reference(self, event_type: AuditEventType, key: str) -> str | None:
        events = self.db.scalars(
            select(IncidentAuditEventRecord).where(
                IncidentAuditEventRecord.incident_id == self.workflow.incident_id,
                IncidentAuditEventRecord.correlation_id == self.workflow.id,
                IncidentAuditEventRecord.event_type == event_type,
            )
        )
        for event in events:
            value = event.event_metadata.get(key)
            if isinstance(value, str):
                return value
        return None
