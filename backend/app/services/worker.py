import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application import ActionExecutionOutcome, ActionService
from app.core.config import Settings, get_settings
from app.core.enums import ApprovalStatus, OperationAction, TargetStatus, TaskStatus
from app.db.base import utc_now
from app.domain.actions.models import ActionRequest, ActionStatus
from app.models import (
    Environment,
    OperationLock,
    OperationRequest,
    OperationTask,
    ServiceStatusSnapshot,
    TaskLog,
    TopologySyncState,
)
from app.repositories.tasks import TaskRepository
from app.services.audit import write_audit
from app.services.execution_policy import WRITE_ACTIONS, PolicyRejection
from app.services.operations import structured_action
from app.services.redaction import redact_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetRun:
    outcome: ActionExecutionOutcome
    attempts: int
    timed_out: bool = False


class WorkerService:
    """Runs validated tasks through an injected portable ActionService."""

    def __init__(
        self,
        db: Session,
        action_service: ActionService,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.action_service = action_service
        self.settings = settings or get_settings()
        self.tasks = TaskRepository(db)

    def run_once(self) -> bool:
        self._recover_stale_work()
        task = self.tasks.claim_next(utc_now())
        if task is None:
            return False
        write_audit(
            self.db,
            "TASK_STATUS_CHANGED",
            "worker",
            "Task entered RUNNING",
            task.id,
            {"from": TaskStatus.PENDING.value, "to": TaskStatus.RUNNING.value},
        )
        self.db.commit()
        try:
            environment = self.db.get(Environment, task.environment_id)
            if environment is None:
                raise RuntimeError("Task environment disappeared")
            approval_granted = self._revalidate_approval(task)
            if task.cancel_requested:
                self._cancel_remaining(task)
            else:
                self._run_targets(task, environment, approval_granted)
            final_status = self._final_status(task)
            task.status = final_status
            task.finished_at = utc_now()
            self._update_topology_sync(task, final_status)
            self._release_locks(task.id)
            self._audit_completion(task, environment, final_status)
            self.db.commit()
            return True
        except PolicyRejection as rejection:
            self.db.rollback()
            self._fail_rejected_task(task.id, rejection)
            return True
        except Exception as exc:
            self.db.rollback()
            self._fail_unexpected_task(task.id, exc)
            return True

    def _revalidate_approval(self, task: object) -> bool:
        action = task.action  # type: ignore[attr-defined]
        if action not in WRITE_ACTIONS or not self.settings.approval_required_for_write:
            return False
        request_id = task.operation_request_id  # type: ignore[attr-defined]
        item = self.db.get(OperationRequest, request_id) if request_id else None
        valid = bool(
            item
            and item.status is ApprovalStatus.APPROVED
            and item.task_id == task.id  # type: ignore[attr-defined]
            and item.action is action
        )
        if not valid:
            raise PolicyRejection(
                "APPROVAL_INVALIDATED",
                "Write approval is missing, revoked, or does not match the task",
                "approval",
            )
        assert item is not None
        write_audit(
            self.db,
            "WRITE_EXECUTION_AUTHORIZED",
            "worker",
            "Approval revalidated before write execution",
            task.id,  # type: ignore[attr-defined]
            {"operation_request_id": item.id},
        )
        return True

    def _run_targets(self, task: object, environment: Environment, approval_granted: bool) -> None:
        for target in list(task.targets):  # type: ignore[attr-defined]
            self.db.refresh(task, ["cancel_requested"])
            if task.cancel_requested:  # type: ignore[attr-defined]
                self._cancel_remaining(task)
                break
            action = structured_action(
                action=task.action,  # type: ignore[attr-defined]
                target=target.host.name,
                service=target.service.name,
                environment_level=environment.environment_level.value,
            )
            run = self._execute_one(action, approval_granted=approval_granted)
            self._apply_target_run(task, target, run)
            self.db.commit()
            if (
                task.partial_failure_policy.value == "NONE"  # type: ignore[attr-defined]
                and target.status is not TargetStatus.SUCCEEDED
            ):
                self._cancel_remaining(task)
                break

    def _execute_one(self, action: ActionRequest, *, approval_granted: bool) -> TargetRun:
        outcome: ActionExecutionOutcome | None = None
        for attempt in range(1, self.settings.executor_retry + 2):
            try:
                outcome = asyncio.run(
                    asyncio.wait_for(
                        self.action_service.execute(
                            action, approval_granted=approval_granted
                        ),
                        timeout=self.settings.execution_timeout_seconds,
                    )
                )
            except TimeoutError:
                return TargetRun(
                    outcome=ActionExecutionOutcome(
                        assessment=self.action_service.policy.assess(
                            action, approval_granted=approval_granted
                        )
                    ),
                    attempts=attempt,
                    timed_out=True,
                )
            if outcome.result is None or outcome.result.status is ActionStatus.SUCCEEDED:
                return TargetRun(outcome=outcome, attempts=attempt)
        assert outcome is not None
        return TargetRun(outcome=outcome, attempts=self.settings.executor_retry + 1)

    def _apply_target_run(self, task: object, target: object, run: TargetRun) -> None:
        target.attempt_count = run.attempts  # type: ignore[attr-defined]
        target.duration_ms = 0  # type: ignore[attr-defined]
        if run.timed_out:
            target.status = TargetStatus.TIMED_OUT  # type: ignore[attr-defined]
            target.error_message = "ACTION_EXECUTION_TIMED_OUT"  # type: ignore[attr-defined]
            return
        result = run.outcome.result
        verification = run.outcome.verification
        if result is None:
            target.status = TargetStatus.FAILED  # type: ignore[attr-defined]
            target.error_message = run.outcome.assessment.reason  # type: ignore[attr-defined]
            return
        succeeded = result.status is ActionStatus.SUCCEEDED
        verified = verification is not None and verification.verified
        target.status = (  # type: ignore[attr-defined]
            TargetStatus.SUCCEEDED if succeeded and verified else TargetStatus.FAILED
        )
        target.output = redact_text(result.summary)  # type: ignore[attr-defined]
        target.verification_status = (  # type: ignore[attr-defined]
            TargetStatus.SUCCEEDED if verified else TargetStatus.FAILED
        )
        target.verification_output = (  # type: ignore[attr-defined]
            redact_text(verification.summary) if verification is not None else None
        )
        self.db.add(
            TaskLog(
                task_id=task.id,  # type: ignore[attr-defined]
                target_id=target.id,  # type: ignore[attr-defined]
                stream="action",
                message=target.output or "",  # type: ignore[attr-defined]
                exit_code=0 if succeeded else 1,
                dry_run=self.action_service.executor.executor_name == "mock",
                created_at=utc_now(),
            )
        )
        self._upsert_snapshot(task, target)
        if run.attempts > 1:
            write_audit(
                self.db,
                "EXECUTOR_RETRIED",
                "worker",
                "Action execution retried",
                task.id,  # type: ignore[attr-defined]
                {"target_id": target.id, "attempts": run.attempts},  # type: ignore[attr-defined]
            )

    def _upsert_snapshot(self, task: object, target: object) -> None:
        snapshot = self.db.scalar(
            select(ServiceStatusSnapshot).where(
                ServiceStatusSnapshot.environment_id == task.environment_id,  # type: ignore[attr-defined]
                ServiceStatusSnapshot.service_id == target.service_id,  # type: ignore[attr-defined]
                ServiceStatusSnapshot.host_id == target.host_id,  # type: ignore[attr-defined]
            )
        )
        if snapshot is None:
            snapshot = ServiceStatusSnapshot(
                environment_id=task.environment_id,  # type: ignore[attr-defined]
                service_id=target.service_id,  # type: ignore[attr-defined]
                host_id=target.host_id,  # type: ignore[attr-defined]
                status=target.status,  # type: ignore[attr-defined]
                task_id=task.id,  # type: ignore[attr-defined]
                observed_at=utc_now(),
                dry_run=self.action_service.executor.executor_name == "mock",
            )
            self.db.add(snapshot)
        else:
            snapshot.status = target.status  # type: ignore[attr-defined]
            snapshot.task_id = task.id  # type: ignore[attr-defined]
            snapshot.observed_at = utc_now()

    @staticmethod
    def _final_status(task: object) -> TaskStatus:
        statuses = {target.status for target in task.targets}  # type: ignore[attr-defined]
        if statuses == {TargetStatus.CANCELLED}:
            return TaskStatus.CANCELLED
        if statuses == {TargetStatus.SUCCEEDED}:
            return TaskStatus.SUCCEEDED
        if statuses == {TargetStatus.TIMED_OUT}:
            return TaskStatus.TIMED_OUT
        if statuses <= {TargetStatus.FAILED, TargetStatus.CANCELLED}:
            return TaskStatus.FAILED
        return TaskStatus.PARTIALLY_SUCCEEDED

    @staticmethod
    def _cancel_remaining(task: object) -> None:
        for target in task.targets:  # type: ignore[attr-defined]
            if target.status is TargetStatus.PENDING:
                target.status = TargetStatus.CANCELLED
                target.error_message = "TASK_CANCELLED"

    def _release_locks(self, task_id: str) -> None:
        self.db.execute(delete(OperationLock).where(OperationLock.task_id == task_id))

    def _recover_stale_work(self) -> None:
        now = utc_now()
        cutoff = now - timedelta(
            seconds=min(self.settings.stale_task_seconds, self.settings.lock_ttl_seconds)
        )
        terminal = {
            TaskStatus.SUCCEEDED,
            TaskStatus.PARTIALLY_SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.TIMED_OUT,
            TaskStatus.CANCELLED,
            TaskStatus.REJECTED,
        }
        stale_tasks = list(
            self.db.scalars(
                select(OperationTask).where(
                    OperationTask.status == TaskStatus.RUNNING,
                    OperationTask.updated_at < cutoff,
                )
            )
        )
        for task in stale_tasks:
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.error_message = None
            write_audit(
                self.db,
                "STALE_TASK_RECOVERED",
                "worker",
                "Stale RUNNING task returned to the queue",
                task.id,
            )
        locks = list(self.db.scalars(select(OperationLock)))
        for lock in locks:
            locked_task = self.tasks.get(lock.task_id)
            if locked_task is None or locked_task.status in terminal:
                self.db.delete(lock)
        if stale_tasks or locks:
            self.db.commit()

    def _update_topology_sync(self, task: object, final_status: TaskStatus) -> None:
        if task.action is not OperationAction.DISCOVER_TOPOLOGY:  # type: ignore[attr-defined]
            return
        sync = self.db.get(TopologySyncState, task.environment_id)  # type: ignore[attr-defined]
        if sync is None:
            sync = TopologySyncState(
                environment_id=task.environment_id,  # type: ignore[attr-defined]
                last_task_id=task.id,  # type: ignore[attr-defined]
                status=final_status,
                last_success_at=(
                    task.finished_at  # type: ignore[attr-defined]
                    if final_status is TaskStatus.SUCCEEDED
                    else None
                ),
                error_message=(
                    None if final_status is TaskStatus.SUCCEEDED else "Topology sync failed"
                ),
                updated_at=utc_now(),
            )
            self.db.add(sync)

    def _audit_completion(
        self, task: object, environment: Environment, final_status: TaskStatus
    ) -> None:
        write_audit(
            self.db,
            "TASK_STATUS_CHANGED",
            "worker",
            f"Task entered {final_status.value}",
            task.id,  # type: ignore[attr-defined]
            {
                "from": TaskStatus.RUNNING.value,
                "to": final_status.value,
                "action": task.action.value,  # type: ignore[attr-defined]
                "environment": environment.code,
                "result": final_status.value,
                "execution_mode": self.action_service.executor.executor_name,
            },
        )

    def _fail_rejected_task(self, task_id: str, rejection: PolicyRejection) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            return
        task.status = TaskStatus.FAILED
        task.error_message = f"{rejection.code}: {rejection.message}"
        task.finished_at = utc_now()
        self._release_locks(task.id)
        write_audit(
            self.db,
            "EXECUTION_REJECTED",
            "worker",
            "Task rejected before action execution",
            task.id,
            {"action": task.action.value, "error_code": rejection.code},
        )
        self.db.commit()

    def _fail_unexpected_task(self, task_id: str, exc: Exception) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            return
        task.status = TaskStatus.FAILED
        task.error_message = redact_text(str(exc))
        task.finished_at = utc_now()
        self._release_locks(task.id)
        write_audit(
            self.db,
            "TASK_STATUS_CHANGED",
            "worker",
            "Task failed unexpectedly",
            task.id,
            {"from": TaskStatus.RUNNING.value, "to": TaskStatus.FAILED.value},
        )
        self.db.commit()
        logger.exception("Worker failed while executing task %s", task.id)
