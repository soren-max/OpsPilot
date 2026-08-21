import json
from datetime import timedelta
from typing import Protocol

from opentelemetry import metrics, trace
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.incident_service import safe_audit_metadata
from app.db.base import utc_now
from app.domain.actions.models import ActionRequest, RiskAssessment
from app.domain.audit.models import ActorType, AuditEventType
from app.domain.execution import (
    ExecutionBackend,
    ExecutionContext,
    ExecutionProfile,
    ExecutionStatus,
)
from app.execution.errors import IndeterminateDispatch
from app.execution.router import ExecutionRouter
from app.repositories.execution_models import (
    ExecutionOutboxRecord,
    ExecutionRecord,
    OutboxStatus,
)
from app.repositories.executions import ExecutionOutboxRepository, ExecutionRepository
from app.repositories.incident_models import IncidentAuditEventRecord
from app.repositories.incidents import AuditEventRepository

tracer = trace.get_tracer("opspilot.execution")
meter = metrics.get_meter("opspilot.execution")
dispatch_total = meter.create_counter("execution_dispatch_total")
dispatch_failures = meter.create_counter("execution_dispatch_failures")
unknown_total = meter.create_counter("execution_unknown_total")
reconciliation_total = meter.create_counter("execution_reconciliation_total")
verification_failure_after_success = meter.create_counter("verification_failure_after_success")
queue_age = meter.create_histogram("execution_queue_age", unit="s")
execution_duration = meter.create_histogram("execution_duration", unit="s")


class ExecutionVerifier(Protocol):
    async def verify(self, execution: ExecutionRecord) -> bool: ...


class ExecutionPlaneService:
    def __init__(self, db: Session, router: ExecutionRouter) -> None:
        self.db = db
        self.router = router
        self.executions = ExecutionRepository(db)
        self.outbox = ExecutionOutboxRepository(db)
        self.audits = AuditEventRepository(db)

    def queue_approved(
        self,
        *,
        incident_id: str,
        workflow_id: str,
        action_fingerprint: str,
        request: ActionRequest,
        assessment: RiskAssessment,
        approval_id: str,
        trace_id: str | None = None,
    ) -> ExecutionRecord:
        if not assessment.allowed:
            raise ValueError("Execution requires an allowed post-approval policy assessment")
        existing = self.executions.find_action(workflow_id, action_fingerprint)
        if existing is not None:
            return existing
        with tracer.start_as_current_span("execution.route") as span:
            route = self.router.route(request, assessment)
            span.set_attribute("backend.type", route.backend_type.value)
            span.set_attribute("execution.profile", route.profile_name)
            span.set_attribute("incident.id", incident_id)
            span.set_attribute("workflow.id", workflow_id)
        now = utc_now()
        record = ExecutionRecord(
            incident_id=incident_id,
            workflow_id=workflow_id,
            action_fingerprint=action_fingerprint,
            backend_type=route.backend_type,
            backend_profile=route.profile_name,
            status=ExecutionStatus.QUEUED,
            attempt=0,
            trace_id=trace_id,
            version=1,
            request_payload=request.model_dump(mode="json"),
            created_at=now,
        )
        try:
            self.executions.add(record)
            self.db.flush()
            self.outbox.add(
                ExecutionOutboxRecord(
                    execution_id=record.id,
                    message_type="execution.dispatch",
                    payload_reference=f"execution:{record.id}",
                    status=OutboxStatus.PENDING,
                    attempts=0,
                    available_at=now,
                    created_at=now,
                )
            )
            self._audit(
                record,
                AuditEventType.EXECUTION_ROUTED,
                "Execution routed by operator-owned configuration",
                {"approval_id": approval_id},
            )
            self._audit(
                record,
                AuditEventType.EXECUTION_QUEUED,
                "Execution and outbox message committed atomically",
                {},
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.executions.find_action(workflow_id, action_fingerprint)
            if existing is None:
                raise
            return existing
        except Exception:
            self.db.rollback()
            raise
        return record

    def _audit(
        self,
        execution: ExecutionRecord,
        event_type: AuditEventType,
        summary: str,
        extra: dict[str, str],
    ) -> None:
        self.audits.append(
            IncidentAuditEventRecord(
                incident_id=execution.incident_id,
                event_type=event_type,
                actor_type=ActorType.SYSTEM,
                actor_id="execution-plane",
                correlation_id=execution.workflow_id,
                occurred_at=utc_now(),
                payload_summary=summary,
                event_metadata=safe_audit_metadata(
                    {
                        "execution_id": execution.id,
                        "backend_type": execution.backend_type.value,
                        "backend_profile": execution.backend_profile,
                        "trace_id": execution.trace_id,
                        **extra,
                    }
                ),
            )
        )


class ExecutionDispatcher:
    def __init__(
        self,
        db: Session,
        *,
        profiles: tuple[ExecutionProfile, ...],
        backends: dict[str, ExecutionBackend],
        verifier: ExecutionVerifier | None = None,
        lease_seconds: int = 60,
    ) -> None:
        self.db = db
        self.profiles = {item.name: item for item in profiles}
        self.backends = backends
        self.verifier = verifier
        self.lease_seconds = lease_seconds
        self.executions = ExecutionRepository(db)
        self.outbox = ExecutionOutboxRepository(db)
        self.audits = AuditEventRepository(db)

    async def dispatch_one(self) -> bool:
        now = utc_now()
        message = self.outbox.claim_one(
            now=now, claimed_until=now + timedelta(seconds=self.lease_seconds)
        )
        if message is None:
            return False
        execution = self.executions.get(message.execution_id, lock=True)
        if execution is None or execution.status is not ExecutionStatus.QUEUED:
            message.status = OutboxStatus.COMPLETED
            message.completed_at = now
            self.db.commit()
            return True
        execution.status = ExecutionStatus.DISPATCHING
        execution.started_at = execution.started_at or now
        execution.attempt += 1
        execution.version += 1
        self._audit(execution, AuditEventType.EXECUTION_DISPATCHED, "Execution dispatch claimed")
        self.db.commit()  # durable dispatch intent before the external side effect
        backend = self.backends[execution.backend_type.value]
        metric_attributes = {"backend.type": execution.backend_type.value}
        dispatch_total.add(1, metric_attributes)
        queue_age.record(max(0.0, (now - execution.created_at).total_seconds()), metric_attributes)
        context = self._context(execution)
        request = ActionRequest.model_validate_json(json.dumps(execution.request_payload))
        with tracer.start_as_current_span("execution.dispatch") as span:
            span.set_attribute("execution.id", execution.id)
            span.set_attribute("backend.type", execution.backend_type.value)
            try:
                submission = await backend.submit(request, context)
            except IndeterminateDispatch as exc:
                unknown_total.add(1, metric_attributes)
                execution.status = ExecutionStatus.UNKNOWN
                execution.failure_category = "INDETERMINATE_DISPATCH"
                execution.safe_failure_message = str(exc)[:500]
                message.status = OutboxStatus.INDETERMINATE
                message.completed_at = utc_now()
                self._audit(
                    execution,
                    AuditEventType.EXECUTION_UNKNOWN,
                    "Dispatch outcome is unknown",
                )
                self.db.commit()
                return True
            except Exception as exc:
                dispatch_failures.add(1, metric_attributes)
                execution.status = ExecutionStatus.FAILED
                execution.failure_category = "DISPATCH_FAILED"
                execution.safe_failure_message = str(exc)[:500]
                execution.finished_at = utc_now()
                message.status = OutboxStatus.COMPLETED
                message.completed_at = utc_now()
                self._audit(execution, AuditEventType.EXECUTION_FAILED, "Execution dispatch failed")
                self.db.commit()
                return True
        execution.provider_execution_id = submission.backend_execution_id
        execution.submitted_at = submission.submitted_at
        execution.status = submission.initial_status
        execution.safe_provider_status = submission.safe_provider_status
        if execution.status in {ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED}:
            execution.finished_at = utc_now()
            execution_duration.record(
                max(0.0, (execution.finished_at - execution.created_at).total_seconds()),
                metric_attributes,
            )
        message.status = OutboxStatus.COMPLETED
        message.completed_at = utc_now()
        self._audit(execution, AuditEventType.EXECUTION_SUBMITTED, "Execution submitted")
        if execution.status is ExecutionStatus.SUCCEEDED:
            self._audit(execution, AuditEventType.EXECUTION_SUCCEEDED, "Execution succeeded")
        elif execution.status is ExecutionStatus.FAILED:
            self._audit(execution, AuditEventType.EXECUTION_FAILED, "Execution failed")
        await self._verify_if_succeeded(execution)
        self.db.commit()
        return True

    def recover_expired_dispatches(self) -> int:
        now = utc_now()
        expired = list(
            self.db.scalars(
                select(ExecutionOutboxRecord).where(
                    ExecutionOutboxRecord.status == OutboxStatus.CLAIMED,
                    ExecutionOutboxRecord.claimed_until < now,
                )
            )
        )
        for message in expired:
            execution = self.executions.get(message.execution_id, lock=True)
            if execution is not None and execution.status is ExecutionStatus.DISPATCHING:
                execution.status = ExecutionStatus.UNKNOWN
                execution.failure_category = "WORKER_CRASH_DURING_DISPATCH"
                execution.safe_failure_message = "Dispatch lease expired; reconcile before retry"
                execution.version += 1
                message.status = OutboxStatus.INDETERMINATE
                message.completed_at = now
                self._audit(
                    execution,
                    AuditEventType.EXECUTION_UNKNOWN,
                    "Dispatch worker lease expired",
                )
        self.db.commit()
        return len(expired)

    def _context(self, execution: ExecutionRecord) -> ExecutionContext:
        profile = self.profiles[execution.backend_profile]
        refs = dict(profile.immutable_refs)
        if execution.provider_execution_id:
            refs["provider_execution_id"] = execution.provider_execution_id
            profile = profile.model_copy(update={"immutable_refs": refs})
        return ExecutionContext(
            execution_id=execution.id,
            incident_id=execution.incident_id,
            workflow_id=execution.workflow_id,
            profile=profile,
            trace_id=execution.trace_id,
        )

    async def _verify_if_succeeded(self, execution: ExecutionRecord) -> None:
        if execution.status is not ExecutionStatus.SUCCEEDED or self.verifier is None:
            return
        with tracer.start_as_current_span("verification.run"):
            verified = await self.verifier.verify(execution)
        execution.verification_status = "SUCCEEDED" if verified else "FAILED"
        if not verified:
            verification_failure_after_success.add(
                1, {"backend.type": execution.backend_type.value}
            )
            self._audit(
                execution,
                AuditEventType.EXECUTION_VERIFICATION_FAILED,
                "Backend succeeded but incident verification failed",
            )

    def _audit(self, execution: ExecutionRecord, kind: AuditEventType, summary: str) -> None:
        self.audits.append(
            IncidentAuditEventRecord(
                incident_id=execution.incident_id,
                event_type=kind,
                actor_type=ActorType.SYSTEM,
                actor_id="execution-dispatcher",
                correlation_id=execution.workflow_id,
                occurred_at=utc_now(),
                payload_summary=summary,
                event_metadata=safe_audit_metadata(
                    {
                        "execution_id": execution.id,
                        "backend_type": execution.backend_type.value,
                        "backend_profile": execution.backend_profile,
                        "provider_execution_id": execution.provider_execution_id,
                        "trace_id": execution.trace_id,
                    }
                ),
            )
        )


class ExecutionReconciler:
    def __init__(self, dispatcher: ExecutionDispatcher) -> None:
        self.dispatcher = dispatcher

    async def reconcile(self, execution_id: str) -> ExecutionRecord:
        execution = self.dispatcher.executions.get(execution_id, lock=True)
        if execution is None:
            raise ValueError("Execution does not exist")
        if execution.status not in {
            ExecutionStatus.QUEUED,
            ExecutionStatus.SUBMITTED,
            ExecutionStatus.RUNNING,
            ExecutionStatus.UNKNOWN,
        }:
            return execution
        backend = self.dispatcher.backends[execution.backend_type.value]
        context = self.dispatcher._context(execution)
        with tracer.start_as_current_span("execution.reconcile"):
            result = await backend.reconcile(context)
        reconciliation_total.add(1, {"backend.type": execution.backend_type.value})
        execution.status = result.status
        execution.provider_execution_id = (
            result.backend_execution_id or execution.provider_execution_id
        )
        execution.safe_provider_status = result.safe_provider_status
        execution.last_reconciled_at = result.reconciled_at
        execution.version += 1
        if execution.status in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        }:
            execution.finished_at = result.reconciled_at
            execution_duration.record(
                max(0.0, (result.reconciled_at - execution.created_at).total_seconds()),
                {"backend.type": execution.backend_type.value},
            )
        self.dispatcher._audit(
            execution, AuditEventType.EXECUTION_RECONCILED, "Execution reconciled"
        )
        terminal_events = {
            ExecutionStatus.SUCCEEDED: (
                AuditEventType.EXECUTION_SUCCEEDED,
                "Execution succeeded",
            ),
            ExecutionStatus.FAILED: (AuditEventType.EXECUTION_FAILED, "Execution failed"),
            ExecutionStatus.UNKNOWN: (
                AuditEventType.EXECUTION_UNKNOWN,
                "Execution remains unknown",
            ),
        }
        if terminal := terminal_events.get(execution.status):
            self.dispatcher._audit(execution, terminal[0], terminal[1])
        await self.dispatcher._verify_if_succeeded(execution)
        self.dispatcher.db.commit()
        return execution
