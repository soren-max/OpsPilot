from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    RiskAssessment,
    RiskLevel,
    ServiceActionParams,
    TargetEnvironment,
)
from app.domain.execution import (
    BackendType,
    ExecutionBackendDescriptor,
    ExecutionContext,
    ExecutionMode,
    ExecutionProfile,
    ExecutionStatus,
    ReconciliationResult,
)
from app.domain.incidents.models import IncidentStatus, Severity
from app.execution.errors import IndeterminateDispatch
from app.execution.router import ExecutionRouter
from app.execution.service import ExecutionDispatcher, ExecutionPlaneService, ExecutionReconciler
from app.repositories.execution_models import ExecutionOutboxRecord, ExecutionRecord, OutboxStatus
from app.repositories.executions import ExecutionOutboxRepository
from app.repositories.incident_models import IncidentRecord
from app.repositories.workflow_models import WorkflowRunRecord, WorkflowRunStatus


def seed_execution(db: Session) -> tuple[ExecutionRecord, ExecutionOutboxRecord, ExecutionProfile]:
    now = utc_now()
    incident = IncidentRecord(
        title="Payments unavailable",
        summary="Current health evidence reports the process unavailable",
        severity=Severity.HIGH,
        status=IncidentStatus.MITIGATING,
        environment="production",
        service="payments",
        source="test",
        created_by="test",
        tags=[],
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(incident)
    db.flush()
    workflow = WorkflowRunRecord(
        incident_id=incident.id,
        graph_name="incident",
        graph_version="1",
        status=WorkflowRunStatus.RUNNING,
        started_by="operator",
        idempotency_key="execution-test",
        state_references={},
        created_at=now,
    )
    db.add(workflow)
    db.flush()
    request = ActionRequest(
        action_type=ActionType.RESTART_SERVICE,
        target="payments-01",
        environment=TargetEnvironment.PRODUCTION,
        parameters=ServiceActionParams(service="payments"),
        reason="current evidence supports a governed restart",
    )
    execution = ExecutionRecord(
        incident_id=incident.id,
        workflow_id=workflow.id,
        action_fingerprint="a" * 64,
        backend_type=BackendType.HARNESS,
        backend_profile="prod-restart",
        status=ExecutionStatus.QUEUED,
        attempt=0,
        version=1,
        request_payload=request.model_dump(mode="json"),
        created_at=now,
    )
    db.add(execution)
    db.flush()
    outbox = ExecutionOutboxRecord(
        execution_id=execution.id,
        message_type="execution.dispatch",
        payload_reference=f"execution:{execution.id}",
        status=OutboxStatus.PENDING,
        attempts=0,
        available_at=now,
        created_at=now,
    )
    db.add(outbox)
    db.commit()
    profile = ExecutionProfile(
        name="prod-restart",
        backend_type=BackendType.HARNESS,
        environment=TargetEnvironment.PRODUCTION,
        allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
        immutable_refs={"pipeline_identifier": "opspilot_restart"},
    )
    return execution, outbox, profile


def test_queue_is_idempotent_for_workflow_action(db: Session) -> None:
    execution, outbox, profile = seed_execution(db)
    db.delete(outbox)
    db.delete(execution)
    db.commit()
    descriptor = ExecutionBackendDescriptor(
        backend_type=BackendType.HARNESS,
        supported_action_types=frozenset({ActionType.RESTART_SERVICE}),
        supported_modes=frozenset({ExecutionMode.REMEDIATE}),
        supported_environments=frozenset({TargetEnvironment.PRODUCTION}),
        supports_async=True,
        supports_status=True,
        supports_cancel=False,
        supports_reconciliation=True,
        max_risk_level=RiskLevel.HIGH,
    )
    router = ExecutionRouter(
        profiles=(profile,),
        descriptors=(descriptor,),
        routes={
            (ActionType.RESTART_SERVICE.value, TargetEnvironment.PRODUCTION.value): profile.name
        },
    )
    request = ActionRequest(
        action_type=ActionType.RESTART_SERVICE,
        target="payments-01",
        environment=TargetEnvironment.PRODUCTION,
        parameters=ServiceActionParams(service="payments"),
        reason="current evidence supports a governed restart",
    )
    allowed = RiskAssessment(
        risk_level=RiskLevel.MEDIUM,
        reason="approved",
        approval_required=False,
        policy_rule="restart-approved-v1",
        allowed=True,
    )
    service = ExecutionPlaneService(db, router)
    first = service.queue_approved(
        incident_id=execution.incident_id,
        workflow_id=execution.workflow_id,
        action_fingerprint="b" * 64,
        request=request,
        assessment=allowed,
        approval_id="approval-1",
    )
    second = service.queue_approved(
        incident_id=execution.incident_id,
        workflow_id=execution.workflow_id,
        action_fingerprint="b" * 64,
        request=request,
        assessment=allowed,
        approval_id="approval-1",
    )
    assert first.id == second.id
    assert db.query(ExecutionOutboxRecord).filter_by(execution_id=first.id).count() == 1


class IndeterminateBackend:
    async def prepare(self, request: object, context: object) -> object:
        raise AssertionError("not used")

    async def submit(self, request: object, context: object) -> object:
        raise IndeterminateDispatch("remote acceptance unknown")

    async def get_status(self, context: ExecutionContext) -> ReconciliationResult:
        return await self.reconcile(context)

    async def reconcile(self, context: ExecutionContext) -> ReconciliationResult:
        return ReconciliationResult(
            execution_id=context.execution_id,
            backend_execution_id="remote-123",
            status=ExecutionStatus.SUCCEEDED,
            reconciled_at=datetime.now(UTC),
            safe_provider_status="SUCCESS",
        )


@pytest.mark.asyncio
async def test_timeout_after_remote_accept_is_not_retried(db: Session) -> None:
    execution, outbox, profile = seed_execution(db)
    backend = IndeterminateBackend()
    dispatcher = ExecutionDispatcher(
        db,
        profiles=(profile,),
        backends={BackendType.HARNESS.value: backend},  # type: ignore[dict-item]
    )
    assert await dispatcher.dispatch_one()
    db.refresh(execution)
    db.refresh(outbox)
    assert execution.status is ExecutionStatus.UNKNOWN
    assert outbox.status is OutboxStatus.INDETERMINATE
    assert execution.attempt == 1
    assert not await dispatcher.dispatch_one()
    assert execution.attempt == 1


def test_expired_claim_is_recovered_not_reclaimed(db: Session) -> None:
    execution, outbox, profile = seed_execution(db)
    execution.status = ExecutionStatus.DISPATCHING
    outbox.status = OutboxStatus.CLAIMED
    outbox.claimed_until = utc_now() - timedelta(seconds=1)
    db.commit()
    repo = ExecutionOutboxRepository(db)
    assert repo.claim_one(now=utc_now(), claimed_until=utc_now() + timedelta(seconds=60)) is None
    dispatcher = ExecutionDispatcher(db, profiles=(profile,), backends={})
    assert dispatcher.recover_expired_dispatches() == 1
    assert execution.status is ExecutionStatus.UNKNOWN
    assert outbox.status is OutboxStatus.INDETERMINATE


@pytest.mark.asyncio
async def test_reconciliation_attaches_provider_without_dispatch(db: Session) -> None:
    execution, outbox, profile = seed_execution(db)
    execution.status = ExecutionStatus.UNKNOWN
    outbox.status = OutboxStatus.INDETERMINATE
    db.commit()
    backend = IndeterminateBackend()
    dispatcher = ExecutionDispatcher(
        db,
        profiles=(profile,),
        backends={BackendType.HARNESS.value: backend},  # type: ignore[dict-item]
    )
    result = await ExecutionReconciler(dispatcher).reconcile(execution.id)
    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.provider_execution_id == "remote-123"
    assert result.last_reconciled_at is not None
    assert db.scalar(select(ExecutionRecord).where(ExecutionRecord.id == execution.id)) is result
