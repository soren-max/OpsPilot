from datetime import UTC, datetime

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.application.approval_service import ApprovalService
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
from app.execution.router import ExecutionRouter
from app.execution.service import ExecutionDispatcher, ExecutionPlaneService
from app.repositories.execution_models import ExecutionOutboxRecord, ExecutionRecord, OutboxStatus
from app.repositories.workflow_models import WorkflowRunStatus
from tests.test_approvals_api import _waiting
from tests.workflows.test_incident_workflow import create_incident, mock_action_service


def test_approved_workflow_uses_durable_execution_outbox(client: object, db: Session) -> None:
    _incident_id, approval_id = _waiting(db, shared_checkpoint=True)

    response = client.post(  # type: ignore[attr-defined]
        f"/api/v1/approvals/{approval_id}/approve",
        json={"reason": "current evidence supports the bounded remediation"},
    )

    assert response.status_code == 200
    execution = db.query(ExecutionRecord).one()
    outbox = db.query(ExecutionOutboxRecord).filter_by(execution_id=execution.id).one()
    assert execution.backend_type is BackendType.MOCK
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.verification_status == "SUCCEEDED"
    assert outbox.status is OutboxStatus.COMPLETED
    assert execution.provider_execution_id == execution.id


class AsyncHarnessFixture:
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

    async def prepare(self, request: object, context: object) -> object:
        raise AssertionError("not used")

    async def submit(self, request: object, context: ExecutionContext) -> ExecutionSubmission:
        execution_id = context.execution_id
        return ExecutionSubmission(
            execution_id=execution_id,
            backend_type=BackendType.HARNESS,
            backend_execution_id="harness-run-1",
            submitted_at=datetime.now(UTC),
            initial_status=ExecutionStatus.SUBMITTED,
        )

    async def get_status(self, context: ExecutionContext) -> ReconciliationResult:
        return await self.reconcile(context)

    async def reconcile(self, context: ExecutionContext) -> ReconciliationResult:
        return ReconciliationResult(
            execution_id=context.execution_id,
            backend_execution_id="harness-run-1",
            status=ExecutionStatus.SUCCEEDED,
            reconciled_at=datetime.now(UTC),
            safe_provider_status="SUCCESS",
        )


class HealthyVerifier:
    async def verify(self, execution: ExecutionRecord) -> bool:
        return True


@pytest.mark.asyncio
async def test_async_execution_waits_for_reconciliation_before_verification(db: Session) -> None:
    incident_id = create_incident(db, "service unavailable")
    action_service = mock_action_service("mock-service")
    profile = ExecutionProfile(
        name="test-harness",
        backend_type=BackendType.HARNESS,
        environment=TargetEnvironment.TEST,
        allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
    )
    backend = AsyncHarnessFixture()
    router = ExecutionRouter(
        profiles=(profile,),
        descriptors=(backend.descriptor,),
        routes={(ActionType.RESTART_SERVICE.value, TargetEnvironment.TEST.value): profile.name},
    )
    plane = ExecutionPlaneService(db, router)
    dispatcher = ExecutionDispatcher(
        db,
        profiles=(profile,),
        backends={BackendType.HARNESS.value: backend},  # type: ignore[dict-item]
        verifier=HealthyVerifier(),
    )
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        action_service=action_service,
        execution_plane=plane,
        execution_dispatcher=dispatcher,
    )
    workflow = service.run(service.start(incident_id, "operator", "async-harness").id)
    approval_id = str(workflow.state_references["approval_id"])
    ApprovalService(db).approve(
        approval_id,
        ApprovalActor(actor_id="operator-2", display_name="Operator Two"),
        "current evidence supports the governed pipeline",
    )
    waiting = service.resume(approval_id)
    assert waiting.status is WorkflowRunStatus.WAITING
    assert waiting.current_node == "execution_pending"
    execution = db.get(ExecutionRecord, waiting.execution_task_id)
    assert execution is not None
    assert execution.status is ExecutionStatus.SUBMITTED

    from app.execution.service import ExecutionReconciler

    await ExecutionReconciler(dispatcher).reconcile(execution.id)
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.verification_status == "SUCCEEDED"
    assert waiting.status is WorkflowRunStatus.WAITING
