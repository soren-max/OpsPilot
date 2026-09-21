from datetime import UTC, datetime

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.application.approval_service import ApprovalService
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.domain.actions.models import ActionType, RiskLevel, TargetEnvironment
from app.domain.approvals import ApprovalActor
from app.domain.execution import (
    BackendType,
    ExecutionBackendDescriptor,
    ExecutionContext,
    ExecutionMode,
    ExecutionProfile,
    ExecutionStatus,
    ExecutionSubmission,
    ReconciliationResult,
)
from app.domain.incidents.models import IncidentStatus
from app.execution.errors import IndeterminateDispatch
from app.execution.router import ExecutionRouter
from app.execution.service import (
    ExecutionDispatcher,
    ExecutionPlaneService,
    ExecutionReconciler,
)
from app.repositories.approval_models import ApprovalRequestRecord
from app.repositories.execution_models import ExecutionOutboxRecord, ExecutionRecord
from app.repositories.workflow_models import WorkflowRunStatus
from tests.workflows.test_incident_workflow import create_incident, mock_action_service

HARNESS_PROFILE = ExecutionProfile(
    name="test-harness",
    backend_type=BackendType.HARNESS,
    environment=TargetEnvironment.TEST,
    allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
)


class AsyncHarness:
    """Async backend that accepts the dispatch, then reports SUCCEEDED on reconciliation."""

    descriptor = ExecutionBackendDescriptor(
        backend_type=BackendType.HARNESS,
        supported_action_types=frozenset({ActionType.RESTART_SERVICE}),
        supported_modes=frozenset({ExecutionMode.REMEDIATE}),
        supported_environments=frozenset({TargetEnvironment.TEST}),
        supports_async=True,
        supports_status=True,
        supports_cancel=False,
        supports_reconciliation=True,
        max_risk_level=RiskLevel.HIGH,
    )

    def __init__(self, *, reconcile_status: ExecutionStatus = ExecutionStatus.SUCCEEDED) -> None:
        self.reconcile_status = reconcile_status
        self.submit_calls = 0

    async def prepare(self, request: object, context: object) -> object:
        raise AssertionError("prepare is not part of the dispatch path")

    async def submit(self, request: object, context: ExecutionContext) -> ExecutionSubmission:
        self.submit_calls += 1
        return ExecutionSubmission(
            execution_id=context.execution_id,
            backend_type=BackendType.HARNESS,
            backend_execution_id="harness-run-1",
            submitted_at=datetime.now(UTC),
            initial_status=ExecutionStatus.SUBMITTED,
        )

    async def reconcile(self, context: ExecutionContext) -> ReconciliationResult:
        return ReconciliationResult(
            execution_id=context.execution_id,
            backend_execution_id="harness-run-1",
            status=self.reconcile_status,
            reconciled_at=datetime.now(UTC),
            safe_provider_status="SUCCESS",
        )


class LostResponseHarness(AsyncHarness):
    """Dispatch outcome is genuinely unknown: the request may have reached the remote system."""

    async def submit(self, request: object, context: ExecutionContext) -> ExecutionSubmission:
        self.submit_calls += 1
        raise IndeterminateDispatch("Response was lost after the request was sent")


class HealthyVerifier:
    def __init__(self, *, verified: bool = True) -> None:
        self.verified = verified

    async def verify(self, execution: ExecutionRecord) -> bool:
        if not self.verified:
            execution.verification_status = "FAILED"
        return self.verified


def build_plane(
    db: Session, backend: AsyncHarness, verifier: HealthyVerifier
) -> tuple[ExecutionPlaneService, ExecutionDispatcher]:
    router = ExecutionRouter(
        profiles=(HARNESS_PROFILE,),
        descriptors=(backend.descriptor,),
        routes={
            (ActionType.RESTART_SERVICE.value, TargetEnvironment.TEST.value): (
                HARNESS_PROFILE.name
            )
        },
    )
    return (
        ExecutionPlaneService(db, router),
        ExecutionDispatcher(
            db,
            profiles=(HARNESS_PROFILE,),
            backends={BackendType.HARNESS.value: backend},  # type: ignore[dict-item]
            verifier=verifier,
        ),
    )


def start_approved(
    db: Session,
    backend: AsyncHarness,
    verifier: HealthyVerifier,
    *,
    evidence: str = "service unavailable",
    key: str = "async-resume",
) -> tuple[WorkflowService, str, str, str]:
    incident_id = create_incident(db, evidence)
    plane, dispatcher = build_plane(db, backend, verifier)
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        action_service=mock_action_service("mock-service"),
        execution_plane=plane,
        execution_dispatcher=dispatcher,
    )
    workflow = service.run(service.start(incident_id, "operator", key).id)
    approval_id = str(workflow.state_references["approval_id"])
    ApprovalService(db).approve(
        approval_id,
        ApprovalActor(actor_id="operator-2", display_name="Operator Two"),
        "current evidence supports the governed pipeline",
    )
    return service, incident_id, workflow.id, approval_id


@pytest.mark.asyncio
async def test_reconciled_success_resumes_to_verification_without_reapproval(db: Session) -> None:
    backend = AsyncHarness()
    service, incident_id, workflow_id, approval_id = start_approved(db, backend, HealthyVerifier())
    waiting = service.resume(approval_id)
    assert waiting.status is WorkflowRunStatus.WAITING
    assert waiting.current_node == "execution_pending"
    execution = db.get(ExecutionRecord, waiting.execution_task_id)
    assert execution is not None
    assert execution.status is ExecutionStatus.SUBMITTED

    await ExecutionReconciler(service.execution_dispatcher).reconcile(execution.id)  # type: ignore[arg-type]
    assert execution.status is ExecutionStatus.SUCCEEDED

    resumed = service.resume_execution(workflow_id)

    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    assert resumed.current_node == "finalize"
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.RESOLVED
    # The already-granted approval was consumed, not re-requested.
    assert db.query(ApprovalRequestRecord).count() == 1
    assert backend.submit_calls == 1
    assert db.query(ExecutionRecord).count() == 1
    assert db.query(ExecutionOutboxRecord).count() == 1


@pytest.mark.asyncio
async def test_unknown_execution_reconciled_to_success_still_reaches_resolution(
    db: Session,
) -> None:
    backend = LostResponseHarness()
    service, incident_id, workflow_id, approval_id = start_approved(
        db, backend, HealthyVerifier(), key="async-unknown"
    )
    waiting = service.resume(approval_id)
    execution = db.get(ExecutionRecord, waiting.execution_task_id)
    assert execution is not None
    assert execution.status is ExecutionStatus.UNKNOWN
    assert execution.failure_category == "INDETERMINATE_DISPATCH"
    # An ambiguous dispatch must never be blindly retried.
    assert backend.submit_calls == 1

    await ExecutionReconciler(service.execution_dispatcher).reconcile(execution.id)  # type: ignore[arg-type]
    assert execution.status is ExecutionStatus.SUCCEEDED

    resumed = service.resume_execution(workflow_id)

    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.RESOLVED
    assert backend.submit_calls == 1
    assert db.query(ApprovalRequestRecord).count() == 1


@pytest.mark.asyncio
async def test_reconciled_failure_does_not_resolve_incident(db: Session) -> None:
    backend = AsyncHarness(reconcile_status=ExecutionStatus.FAILED)
    service, incident_id, workflow_id, approval_id = start_approved(
        db, backend, HealthyVerifier(), key="async-failed"
    )
    waiting = service.resume(approval_id)
    await ExecutionReconciler(  # type: ignore[arg-type]
        service.execution_dispatcher  # type: ignore[arg-type]
    ).reconcile(waiting.execution_task_id)

    resumed = service.resume_execution(workflow_id)

    assert resumed.status is WorkflowRunStatus.FAILED
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.FAILED


@pytest.mark.asyncio
async def test_verification_failure_after_success_is_never_resolved(db: Session) -> None:
    backend = AsyncHarness()
    service, incident_id, workflow_id, approval_id = start_approved(
        db, backend, HealthyVerifier(verified=False), key="async-verify-failed"
    )
    waiting = service.resume(approval_id)
    await ExecutionReconciler(  # type: ignore[arg-type]
        service.execution_dispatcher  # type: ignore[arg-type]
    ).reconcile(waiting.execution_task_id)

    resumed = service.resume_execution(workflow_id)

    assert resumed.status is WorkflowRunStatus.FAILED
    assert IncidentService(db)._require(incident_id).status is not IncidentStatus.RESOLVED


@pytest.mark.asyncio
async def test_duplicate_resume_execution_is_idempotent(db: Session) -> None:
    backend = AsyncHarness()
    service, _incident_id, workflow_id, approval_id = start_approved(
        db, backend, HealthyVerifier(), key="async-idempotent"
    )
    waiting = service.resume(approval_id)
    await ExecutionReconciler(  # type: ignore[arg-type]
        service.execution_dispatcher  # type: ignore[arg-type]
    ).reconcile(waiting.execution_task_id)

    first = service.resume_execution(workflow_id)
    second = service.resume_execution(workflow_id)

    assert first.status is WorkflowRunStatus.SUCCEEDED
    assert second.status is WorkflowRunStatus.SUCCEEDED
    assert backend.submit_calls == 1
    assert db.query(ExecutionRecord).count() == 1
    assert db.query(ExecutionOutboxRecord).count() == 1


@pytest.mark.asyncio
async def test_in_flight_execution_keeps_workflow_waiting(db: Session) -> None:
    backend = AsyncHarness()
    service, _incident_id, workflow_id, approval_id = start_approved(
        db, backend, HealthyVerifier(), key="async-inflight"
    )
    waiting = service.resume(approval_id)
    assert waiting.status is WorkflowRunStatus.WAITING

    # No reconciliation yet: the workflow must not guess a terminal outcome.
    still_waiting = service.resume_execution(workflow_id)

    assert still_waiting.status in {WorkflowRunStatus.WAITING, WorkflowRunStatus.RUNNING}
    assert backend.submit_calls == 1


def test_read_only_status_check_bypasses_write_execution_router(db: Session) -> None:
    incident_id = create_incident(db, "read-only-check requested")
    backend = AsyncHarness()
    plane, dispatcher = build_plane(db, backend, HealthyVerifier())
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        action_service=mock_action_service("mock-service"),
        execution_plane=plane,
        execution_dispatcher=dispatcher,
    )

    result = service.run(service.start(incident_id, "operator", "read-only-plane").id)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.last_error is None
    assert IncidentService(db)._require(incident_id).status is IncidentStatus.RESOLVED
    # A read-only check is evidence collection; it never becomes a write execution record.
    assert db.query(ExecutionRecord).count() == 0
    assert backend.submit_calls == 0