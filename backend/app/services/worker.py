import logging
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import (
    ApprovalStatus,
    OperationAction,
    PartialFailurePolicy,
    TargetStatus,
    TaskStatus,
)
from app.db.base import utc_now
from app.executors.base import ExecutionResult, ExecutionTarget, Executor
from app.models import (
    Environment,
    Host,
    OperationLock,
    OperationRequest,
    OperationsIntegrationConfig,
    OperationTask,
    Service,
    ServiceStatusSnapshot,
    TaskLog,
    TopologySyncState,
)
from app.repositories.tasks import TaskRepository
from app.services.audit import write_audit
from app.services.execution_policy import WRITE_ACTIONS, PolicyRejection, validate_execution_target
from app.services.integration_config import (
    active_config,
    build_config_executor,
    dynamic_allowlists,
    read_config,
)
from app.services.redaction import redact_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetRun:
    result: ExecutionResult
    attempts: int
    verification: ExecutionResult | None


class ConfigurationTestWorker:
    """Synchronous, status-only worker path used by the administrator test API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run_status(
        self,
        config: OperationsIntegrationConfig,
        environment: Environment,
        host: Host,
        service: Service,
    ) -> ExecutionResult:
        executor = build_config_executor(config, host, self.settings)
        return executor.execute(
            OperationAction.STATUS,
            ExecutionTarget(
                environment=environment.code,
                host=host.name,
                service=service.name,
                mock_behavior="success",
            ),
            {
                "task_id": f"config-test-{config.id}",
                "parameters": {},
                "timeout_seconds": config.timeout_seconds,
            },
        )


class WorkerService:
    def __init__(self, db: Session, executor: Executor, settings: Settings | None = None) -> None:
        self.db = db
        self.executor = executor
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
        targets = list(task.targets)  # type: ignore[attr-defined]
        runtime_config = active_config(self.db, environment.id)
        if read_config(self.db, environment.id) is not None and runtime_config is None:
            raise PolicyRejection(
                "CONFIG_NOT_READY",
                "Dynamic operations integration configuration is not READY and enabled",
                "environment",
            )
        runtime_allowlists = dynamic_allowlists(runtime_config)
        limit = self.settings.batch_concurrency_limit
        stop_scheduling = False
        for offset in range(0, len(targets), limit):
            self.db.refresh(task, ["cancel_requested"])
            if task.cancel_requested or stop_scheduling:  # type: ignore[attr-defined]
                self._cancel_remaining(task)
                break
            batch = [
                item
                for item in targets[offset : offset + limit]
                if item.status is TargetStatus.PENDING
            ]
            requests: list[tuple[object, ExecutionTarget, Executor]] = []
            for target in batch:
                validate_execution_target(
                    self.settings,
                    action=task.action,  # type: ignore[attr-defined]
                    environment=environment.code,
                    host=target.host.name,
                    service=target.service.name,
                    environment_level=environment.environment_level,
                    approval_granted=approval_granted,
                    require_execution_acknowledgement=runtime_config is not None,
                    **runtime_allowlists,
                )
                requests.append(
                    (
                        target,
                        ExecutionTarget(
                            environment=environment.code,
                            service=target.service.name,
                            host=target.host.name,
                            mock_behavior=target.host.mock_behavior,
                        ),
                        (
                            build_config_executor(runtime_config, target.host, self.settings)
                            if runtime_config is not None
                            else self.executor
                        ),
                    )
                )
            with ThreadPoolExecutor(max_workers=limit) as pool:
                futures = [
                    (
                        target,
                        pool.submit(
                            self._execute_one,
                            target_executor,
                            task.action,  # type: ignore[attr-defined]
                            execution_target,
                            task.id,  # type: ignore[attr-defined]
                            task.parameters,  # type: ignore[attr-defined]
                        ),
                    )
                    for target, execution_target, target_executor in requests
                ]
                pending = {future: target for target, future in futures}
                while pending:
                    completed, _ = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                    self.db.refresh(task, ["cancel_requested"])
                    if task.cancel_requested:  # type: ignore[attr-defined]
                        cancel = getattr(self.executor, "cancel", None)
                        if callable(cancel):
                            cancel(task.id)  # type: ignore[attr-defined]
                    for future in completed:
                        target = pending.pop(future)
                        self._apply_target_run(task, target, future.result())
            self.db.commit()
            if (
                task.partial_failure_policy is PartialFailurePolicy.NONE  # type: ignore[attr-defined]
                and any(target.status is not TargetStatus.SUCCEEDED for target in batch)
            ):
                stop_scheduling = True

    def _execute_one(
        self,
        executor: Executor,
        action: OperationAction,
        target: ExecutionTarget,
        task_id: str,
        parameters: dict[str, object],
    ) -> TargetRun:
        result: ExecutionResult | None = None
        attempts = 0
        for attempt_index in range(1, self.settings.executor_retry + 2):
            attempts = attempt_index
            result = executor.execute(
                action,
                target,
                {
                    "task_id": task_id,
                    "parameters": parameters,
                    "timeout_seconds": self.settings.execution_timeout_seconds,
                },
            )
            if result.success or not result.retryable:
                break
        assert result is not None
        verification = None
        if action in WRITE_ACTIONS:
            verification = executor.execute(
                OperationAction.STATUS,
                target,
                {
                    "task_id": task_id,
                    "parameters": {},
                    "timeout_seconds": self.settings.execution_timeout_seconds,
                },
            )
        return TargetRun(result=result, attempts=attempts, verification=verification)

    def _apply_target_run(self, task: object, target: object, run: TargetRun) -> None:
        result = run.result
        target.status = result.status  # type: ignore[attr-defined]
        hostnames = (target.host.name,)  # type: ignore[attr-defined]
        accounts = (task.requested_by,)  # type: ignore[attr-defined]
        target.output = redact_text(  # type: ignore[attr-defined]
            result.output, hostnames=hostnames, accounts=accounts
        )
        target.error_message = redact_text(  # type: ignore[attr-defined]
            result.error_message, hostnames=hostnames, accounts=accounts
        )
        target.duration_ms = result.duration_ms  # type: ignore[attr-defined]
        target.attempt_count = run.attempts  # type: ignore[attr-defined]
        self._add_logs(
            task.id,  # type: ignore[attr-defined]
            target.id,  # type: ignore[attr-defined]
            result,
            hostnames=hostnames,
            accounts=accounts,
        )
        if run.attempts > 1:
            write_audit(
                self.db,
                "EXECUTOR_RETRIED",
                "worker",
                "Executor retried an explicitly retryable failure",
                task.id,  # type: ignore[attr-defined]
                {"target_id": target.id, "attempts": run.attempts},  # type: ignore[attr-defined]
            )
        if run.verification is not None:
            verification = run.verification
            target.verification_status = verification.status  # type: ignore[attr-defined]
            target.verification_output = redact_text(  # type: ignore[attr-defined]
                verification.output, hostnames=hostnames, accounts=accounts
            )
            self._add_logs(
                task.id,  # type: ignore[attr-defined]
                target.id,  # type: ignore[attr-defined]
                verification,
                stream_prefix="verification_",
                hostnames=hostnames,
                accounts=accounts,
            )
            self._upsert_snapshot(task, target, verification)
            if result.success and not verification.success:
                target.status = TargetStatus.FAILED  # type: ignore[attr-defined]
                target.error_message = "STATUS_VERIFICATION_FAILED"  # type: ignore[attr-defined]
            write_audit(
                self.db,
                "WRITE_STATUS_VERIFIED",
                "worker",
                "Status verification completed after write operation",
                task.id,  # type: ignore[attr-defined]
                {
                    "target_id": target.id,  # type: ignore[attr-defined]
                    "verification_status": verification.status.value,
                },
            )
        else:
            self._upsert_snapshot(task, target, result)
        reported = (
            run.verification.service_state if run.verification is not None else result.service_state
        )
        if reported:
            target.host.last_status = reported  # type: ignore[attr-defined]

    def _upsert_snapshot(self, task: object, target: object, result: ExecutionResult) -> None:
        action = task.action  # type: ignore[attr-defined]
        if (
            action
            not in {
                OperationAction.STATUS,
                OperationAction.STATUS_ALL,
                OperationAction.STATUS_SERVICE,
                OperationAction.STATUS_SERVICE_HOSTS,
            }
            and action not in WRITE_ACTIONS
        ):
            return
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
                status=result.status,
                task_id=task.id,  # type: ignore[attr-defined]
                observed_at=utc_now(),
                dry_run=result.dry_run,
            )
            self.db.add(snapshot)
        else:
            snapshot.status = result.status
            snapshot.task_id = task.id  # type: ignore[attr-defined]
            snapshot.observed_at = utc_now()
            snapshot.dry_run = result.dry_run

    def _add_logs(
        self,
        task_id: str,
        target_id: str,
        result: ExecutionResult,
        stream_prefix: str = "",
        hostnames: tuple[str, ...] = (),
        accounts: tuple[str, ...] = (),
    ) -> None:
        for stream, message in (
            (f"{stream_prefix}stdout", result.output or ""),
            (f"{stream_prefix}stderr", result.error_message or ""),
        ):
            self.db.add(
                TaskLog(
                    task_id=task_id,
                    target_id=target_id,
                    stream=stream,
                    message=redact_text(message, hostnames=hostnames, accounts=accounts) or "",
                    exit_code=result.exit_code,
                    dry_run=result.dry_run,
                    created_at=utc_now(),
                )
            )

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
        """Recover abandoned RUNNING tasks and remove orphan/terminal target locks."""
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
        else:
            sync.last_task_id = task.id  # type: ignore[attr-defined]
            sync.status = final_status
            sync.updated_at = utc_now()

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
                "requested_by": task.requested_by,  # type: ignore[attr-defined]
                "result": final_status.value,
                "execution_mode": "mock" if self.executor.executor_type == "mock" else "real",
                "partial_failure_policy": task.partial_failure_policy.value,  # type: ignore[attr-defined]
                "targets": [
                    {
                        "service": target.service.name,
                        "host": target.host.name,
                        "status": target.status.value,
                        "duration_ms": target.duration_ms,
                        "attempt_count": target.attempt_count,
                        "verification_status": (
                            target.verification_status.value if target.verification_status else None
                        ),
                    }
                    for target in task.targets  # type: ignore[attr-defined]
                ],
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
            "Task rejected before executor invocation",
            task.id,
            {"action": task.action.value, "error_code": rejection.code},
        )
        self.db.commit()
        logger.warning("Worker rejected task %s: %s", task.id, rejection.code)

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
