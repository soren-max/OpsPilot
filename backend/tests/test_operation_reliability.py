import threading
import time
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import OperationAction, PartialFailurePolicy, TargetStatus, TaskStatus
from app.db.base import utc_now
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.executors.mock import MockExecutor
from app.models import AuditLog, OperationLock, OperationTask
from app.schemas import OperationCreate
from app.services import operations as operations_module
from app.services.operations import OperationService
from app.services.worker import WorkerService

ENV = "00000000-0000-0000-0000-000000000001"
SERVICE = "20000000-0000-0000-0000-000000000001"
HOST_OK = "10000000-0000-0000-0000-000000000001"
HOST_FAIL = "10000000-0000-0000-0000-000000000002"
HOST_TIMEOUT = "10000000-0000-0000-0000-000000000003"


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "write_operations_enabled": True,
        "approval_required_for_write": False,
        "production_operations_enabled": False,
        "allowed_actions": "status,start,stop",
        "batch_concurrency_limit": 1,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def payload(
    action: str = "status",
    hosts: list[str] | None = None,
    policy: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "environment_id": ENV,
        "action": action,
        "scope": "service_hosts",
        "service_id": SERVICE,
        "host_ids": hosts or [HOST_OK],
        "parameters": {},
    }
    if policy:
        body["partial_failure_policy"] = policy
    return body


def test_task_idempotency_replays_and_rejects_changed_payload(client) -> None:
    headers = {"Idempotency-Key": "status-replay-0001"}
    first = client.post("/api/v1/operations", json=payload(), headers=headers)
    second = client.post("/api/v1/operations", json=payload(), headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["data"]["task_id"] == second.json()["data"]["task_id"]

    changed = client.post("/api/v1/operations", json=payload(hosts=[HOST_FAIL]), headers=headers)
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_write_mutex_conflict_and_pending_cancellation_release_lock(
    client, db: Session, mock_write_settings: Settings, monkeypatch
) -> None:
    monkeypatch.setattr(operations_module, "get_settings", lambda: mock_write_settings)
    first = client.post(
        "/api/v1/operations",
        json=payload("start"),
        headers={"Idempotency-Key": "mutex-write-0001"},
    )
    assert first.status_code == 202
    task_id = first.json()["data"]["task_id"]
    conflict = client.post(
        "/api/v1/operations",
        json=payload("stop"),
        headers={"Idempotency-Key": "mutex-write-0002"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "TARGET_LOCK_CONFLICT"

    cancelled = client.post(f"/api/v1/tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "CANCELLED"
    assert db.scalar(select(func.count()).select_from(OperationLock)) == 0
    replacement = client.post(
        "/api/v1/operations",
        json=payload("stop"),
        headers={"Idempotency-Key": "mutex-write-0003"},
    )
    assert replacement.status_code == 202


def test_partial_failure_policies_and_write_status_verification(db: Session) -> None:
    configured = settings()
    none_task = OperationService(db, configured).create(
        OperationCreate.model_validate(payload("start", [HOST_OK, HOST_FAIL, HOST_TIMEOUT]))
    )
    assert WorkerService(db, MockExecutor(), configured).run_once()
    none_task = OperationService(db, configured).tasks.get(none_task.id)
    assert none_task is not None
    assert none_task.partial_failure_policy is PartialFailurePolicy.NONE
    assert [target.status for target in none_task.targets] == [
        TargetStatus.SUCCEEDED,
        TargetStatus.FAILED,
        TargetStatus.CANCELLED,
    ]
    assert none_task.targets[0].verification_status is TargetStatus.SUCCEEDED
    assert none_task.targets[0].verification_output

    best_task = OperationService(db, configured).create(
        OperationCreate.model_validate(
            payload(
                "start",
                [HOST_OK, HOST_FAIL, HOST_TIMEOUT],
                PartialFailurePolicy.BEST_EFFORT.value,
            )
        )
    )
    assert WorkerService(db, MockExecutor(), configured).run_once()
    best_task = OperationService(db, configured).tasks.get(best_task.id)
    assert best_task is not None
    assert all(target.attempt_count == 1 for target in best_task.targets)
    assert TargetStatus.CANCELLED not in {target.status for target in best_task.targets}


class RetryThenSucceedExecutor(BaseExecutor):
    executor_type = "mock"
    supported_actions = frozenset({OperationAction.START, OperationAction.STATUS})

    def __init__(self) -> None:
        self.start_calls = 0
        self.status_calls = 0

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.action is OperationAction.STATUS:
            self.status_calls += 1
            return ExecutionResult(
                TargetStatus.SUCCEEDED, "verified", None, 1, service_state="RUNNING"
            )
        self.start_calls += 1
        if self.start_calls == 1:
            return ExecutionResult(
                TargetStatus.FAILED,
                None,
                "temporary",
                1,
                error_code="EXECUTOR_TEMPORARY_FAILURE",
                retryable=True,
            )
        return ExecutionResult(TargetStatus.SUCCEEDED, "started", None, 1, service_state="RUNNING")


def test_executor_retry_only_uses_explicit_retryable_signal(db: Session) -> None:
    configured = settings(executor_retry=3)
    task = OperationService(db, configured).create(OperationCreate.model_validate(payload("start")))
    executor = RetryThenSucceedExecutor()
    assert WorkerService(db, executor, configured).run_once()
    task = OperationService(db, configured).tasks.get(task.id)
    assert task is not None
    assert task.targets[0].attempt_count == 2
    assert executor.start_calls == 2
    assert executor.status_calls == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.event_type == "EXECUTOR_RETRIED")
        )
        == 1
    )


class ConcurrencyTrackingExecutor(BaseExecutor):
    executor_type = "mock"
    supported_actions = frozenset({OperationAction.STATUS})

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.03)
        with self.lock:
            self.active -= 1
        return ExecutionResult(TargetStatus.SUCCEEDED, "ok", None, 1)


def test_batch_concurrency_never_exceeds_configured_limit(db: Session) -> None:
    configured = settings(batch_concurrency_limit=2)
    task = OperationService(db, configured).create(
        OperationCreate.model_validate(payload("status", [HOST_OK, HOST_FAIL, HOST_TIMEOUT]))
    )
    executor = ConcurrencyTrackingExecutor()
    assert WorkerService(db, executor, configured).run_once()
    assert executor.max_active == 2
    refreshed = db.get(OperationTask, task.id)
    assert refreshed is not None


def test_stale_running_task_and_lock_are_recovered(db: Session) -> None:
    configured = settings(stale_task_seconds=10, lock_ttl_seconds=30)
    task = OperationService(db, configured).create(OperationCreate.model_validate(payload("start")))
    task.status = TaskStatus.RUNNING
    task.started_at = utc_now() - timedelta(seconds=60)
    task.updated_at = utc_now() - timedelta(seconds=60)
    db.commit()

    assert WorkerService(db, MockExecutor(), configured).run_once()
    refreshed = db.get(OperationTask, task.id)
    assert refreshed is not None and refreshed.status is TaskStatus.SUCCEEDED
    assert db.scalar(select(func.count()).select_from(OperationLock)) == 0
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.event_type == "STALE_TASK_RECOVERED")
        )
        == 1
    )
