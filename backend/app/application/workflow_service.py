from __future__ import annotations

from typing import cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.errors import LLMFailure
from app.application.action_service import ActionService
from app.capabilities import IncidentCapabilities
from app.core.errors import ConflictError, NotFoundError
from app.db.base import utc_now
from app.domain.audit.models import AuditEventType
from app.domain.incidents.models import IncidentStatus
from app.repositories.workflow_models import (
    WorkflowEvaluationRecord,
    WorkflowRunRecord,
    WorkflowRunStatus,
)
from app.repositories.workflows import WorkflowEvaluationRepository, WorkflowRunRepository
from app.schemas_workflows import WorkflowTimelineItem
from app.services.redaction import redact_text
from app.workflows.incident.context import IncidentWorkflowContext, IncidentWorkflowRuntime
from app.workflows.incident.errors import (
    DomainFailure,
    WorkflowFailure,
    WorkflowInfrastructureFailure,
)
from app.workflows.incident.graph import GRAPH_NAME, GRAPH_VERSION, build_incident_graph
from app.workflows.incident.investigator import DeterministicInvestigator, IncidentInvestigator
from app.workflows.incident.state import IncidentWorkflowState, WorkflowStatus, initial_state


class WorkflowService:
    def __init__(
        self,
        db: Session,
        *,
        investigator: IncidentInvestigator | None = None,
        checkpointer: BaseCheckpointSaver[str] | None = None,
        action_service: ActionService | None = None,
        capabilities: IncidentCapabilities | None = None,
    ) -> None:
        self.db = db
        self.runs = WorkflowRunRepository(db)
        self.evaluations = WorkflowEvaluationRepository(db)
        self.investigator = investigator or DeterministicInvestigator()
        self.checkpointer = checkpointer or InMemorySaver()
        self.action_service = action_service
        self.capabilities = capabilities

    def start(self, incident_id: str, actor: str, idempotency_key: str) -> WorkflowRunRecord:
        from app.application.incident_service import IncidentService

        incident = IncidentService(self.db)._require(incident_id)
        if incident.status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
            raise ConflictError(
                "INCIDENT_NOT_ACTIONABLE",
                "Resolved or closed incidents cannot start remediation workflows",
            )
        existing = self.runs.find_idempotent(incident_id, actor, idempotency_key)
        if existing is not None:
            return existing
        item = WorkflowRunRecord(
            incident_id=incident_id,
            graph_name=GRAPH_NAME,
            graph_version=GRAPH_VERSION,
            status=WorkflowRunStatus.PENDING,
            started_by=actor,
            idempotency_key=idempotency_key,
            state_references={},
            created_at=utc_now(),
        )
        try:
            self.runs.add(item)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.runs.find_idempotent(incident_id, actor, idempotency_key)
            if existing is None:
                raise
            return existing
        return item

    def run(self, workflow_id: str) -> WorkflowRunRecord:
        workflow = self._require(workflow_id)
        if workflow.status in {
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.WAITING,
        }:
            return workflow
        workflow.status = WorkflowRunStatus.RUNNING
        workflow.started_at = workflow.started_at or utc_now()
        runtime = IncidentWorkflowRuntime(
            self.db, workflow, self.investigator, self.action_service, self.capabilities
        )
        graph = build_incident_graph(self.checkpointer)
        try:
            runtime.audit_workflow(
                AuditEventType.WORKFLOW_STARTED, "Incident workflow started", "RUNNING"
            )
            result = graph.invoke(
                initial_state(workflow.incident_id, workflow.id),
                config={"configurable": {"thread_id": workflow.id}},
                context=IncidentWorkflowContext(runtime=runtime),
            )
            state = cast(IncidentWorkflowState, result)
            self._apply_result(workflow, state, runtime)
        except Exception as exc:
            self.db.rollback()
            workflow = self._require(workflow_id)
            workflow.status = WorkflowRunStatus.FAILED
            workflow.finished_at = utc_now()
            workflow.last_error = self._safe_error(exc)
            runtime = IncidentWorkflowRuntime(
                self.db,
                workflow,
                self.investigator,
                self.action_service,
                self.capabilities,
            )
            runtime.audit_workflow(
                AuditEventType.WORKFLOW_FAILED,
                "Incident workflow failed",
                workflow.last_error,
            )
        self.db.commit()
        return workflow

    def run_next(self) -> bool:
        workflow = self.runs.claim_next()
        if workflow is None:
            return False
        self.db.commit()
        self.run(workflow.id)
        return True

    def cancel(self, workflow_id: str) -> WorkflowRunRecord:
        workflow = self._require(workflow_id)
        if workflow.status in {WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.FAILED}:
            raise ConflictError("WORKFLOW_TERMINAL", "Completed workflows cannot be cancelled")
        if workflow.status is WorkflowRunStatus.RUNNING:
            raise ConflictError(
                "WORKFLOW_RUNNING",
                "Running workflows cannot be cancelled until cooperative cancellation is added",
            )
        if workflow.status is not WorkflowRunStatus.CANCELLED:
            workflow.status = WorkflowRunStatus.CANCELLED
            workflow.finished_at = utc_now()
            self.db.commit()
        return workflow

    def list_for_incident(self, incident_id: str) -> list[WorkflowRunRecord]:
        from app.application.incident_service import IncidentService

        IncidentService(self.db)._require(incident_id)
        return self.runs.list_for_incident(incident_id)

    def timeline(self, workflow_id: str) -> list[WorkflowTimelineItem]:
        self._require(workflow_id)
        return [
            WorkflowTimelineItem(
                id=item.event_id,
                event_type=item.event_type.value,
                occurred_at=item.occurred_at,
                summary=item.payload_summary,
                node=self._metadata_str(item.event_metadata, "node"),
                duration_ms=self._metadata_int(item.event_metadata, "duration_ms"),
                result_status=self._metadata_str(item.event_metadata, "result_status"),
            )
            for item in self.runs.list_audit_events(workflow_id)
        ]

    def get(self, workflow_id: str) -> WorkflowRunRecord:
        return self._require(workflow_id)

    def record_evaluation(
        self, workflow_id: str, expected_outcome: str, actual_outcome: str
    ) -> WorkflowEvaluationRecord:
        workflow = self._require(workflow_id)
        if not expected_outcome or not actual_outcome:
            raise ValueError("Evaluation outcomes must not be empty")
        if len(expected_outcome) > 500 or len(actual_outcome) > 500:
            raise ValueError("Evaluation outcomes must not exceed 500 characters")
        item = WorkflowEvaluationRecord(
            incident_id=workflow.incident_id,
            workflow_id=workflow.id,
            expected_outcome=expected_outcome,
            actual_outcome=actual_outcome,
            created_at=utc_now(),
        )
        self.evaluations.add(item)
        self.db.commit()
        return item

    def _apply_result(
        self,
        workflow: WorkflowRunRecord,
        state: IncidentWorkflowState,
        runtime: IncidentWorkflowRuntime,
    ) -> None:
        workflow.current_node = state["current_node"]
        workflow.last_error = state["last_error"]
        workflow.state_references = {
            **workflow.state_references,
            "workflow_id": workflow.id,
            "diagnosis_id": state["diagnosis_id"],
            "action_fingerprint": workflow.proposed_action_id,
            "execution_task_id": state["execution_task_id"],
            "verification_status": state["verification_status"],
        }
        if state["workflow_status"] == WorkflowStatus.WAITING_APPROVAL.value:
            workflow.status = WorkflowRunStatus.WAITING
            return
        workflow.finished_at = utc_now()
        if state["workflow_status"] == WorkflowStatus.SUCCEEDED.value:
            workflow.status = WorkflowRunStatus.SUCCEEDED
            runtime.audit_workflow(
                AuditEventType.WORKFLOW_COMPLETED,
                "Incident workflow completed",
                WorkflowStatus.SUCCEEDED.value,
            )
        else:
            workflow.status = WorkflowRunStatus.FAILED
            runtime.audit_workflow(
                AuditEventType.WORKFLOW_FAILED,
                "Incident workflow failed",
                state["last_error"] or WorkflowStatus.FAILED.value,
            )

    def _require(self, workflow_id: str) -> WorkflowRunRecord:
        item = self.runs.get(workflow_id)
        if item is None:
            raise NotFoundError("Workflow does not exist")
        return item

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        classified: WorkflowFailure
        if isinstance(exc, WorkflowFailure):
            classified = exc
        elif isinstance(exc, LLMFailure):
            code = exc.code
            safe = redact_text(str(exc)) or "LLM investigation failure"
            return f"{code}: {safe}"[:1000]
        elif isinstance(exc, (ConflictError, NotFoundError, ValueError)):
            classified = DomainFailure(str(exc))
        else:
            classified = WorkflowInfrastructureFailure(str(exc))
        code = classified.code
        safe = redact_text(str(exc)) or "Workflow infrastructure failure"
        return f"{code}: {safe}"[:1000]

    @staticmethod
    def _metadata_str(metadata: dict[str, object], key: str) -> str | None:
        value = metadata.get(key)
        return value if isinstance(value, str) else None

    @staticmethod
    def _metadata_int(metadata: dict[str, object], key: str) -> int | None:
        value = metadata.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else None
