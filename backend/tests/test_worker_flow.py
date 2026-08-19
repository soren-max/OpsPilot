import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import OperationAction, TargetStatus, TaskStatus
from app.db.base import utc_now
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.executors.mock import MockExecutor
from app.models import AuditLog
from app.schemas import OperationCreate
from app.services.operations import OperationService
from app.services.worker import WorkerService

ENV = "00000000-0000-0000-0000-000000000001"
SERVICE = "20000000-0000-0000-0000-000000000001"
HOST_OK = "10000000-0000-0000-0000-000000000001"
HOST_FAIL = "10000000-0000-0000-0000-000000000002"
HOST_TIMEOUT = "10000000-0000-0000-0000-000000000003"


def create(db: Session, hosts: list[str]) -> str:
    task = OperationService(db).create(
        OperationCreate(
            environment_id=ENV,
            action="status",
            scope="service_hosts",
            service_id=SERVICE,
            host_ids=hosts,
        )
    )
    return task.id


def test_worker_success_and_audit(db: Session) -> None:
    task_id = create(db, [HOST_OK])
    assert WorkerService(db, MockExecutor()).run_once()
    task = OperationService(db).tasks.get(task_id)
    assert task is not None and task.status is TaskStatus.SUCCEEDED
    audits = list(db.scalars(select(AuditLog).where(AuditLog.task_id == task_id)))
    assert [item.event_type for item in audits] == [
        "TASK_CREATED",
        "TASK_STATUS_CHANGED",
        "TASK_STATUS_CHANGED",
    ]


def test_worker_partial_failure(db: Session) -> None:
    task_id = create(db, [HOST_OK, HOST_FAIL])
    WorkerService(db, MockExecutor()).run_once()
    task = OperationService(db).tasks.get(task_id)
    assert task is not None and task.status is TaskStatus.PARTIALLY_SUCCEEDED


def test_worker_full_failure(db: Session) -> None:
    task_id = create(db, [HOST_FAIL])
    WorkerService(db, MockExecutor()).run_once()
    task = OperationService(db).tasks.get(task_id)
    assert task is not None and task.status is TaskStatus.FAILED


def test_worker_timeout(db: Session) -> None:
    task_id = create(db, [HOST_TIMEOUT])
    WorkerService(db, MockExecutor()).run_once()
    task = OperationService(db).tasks.get(task_id)
    assert task is not None and task.status is TaskStatus.TIMED_OUT


class TimeoutCaptureExecutor(BaseExecutor):
    executor_type = "mock"
    supported_actions = frozenset({OperationAction.STATUS})

    def __init__(self) -> None:
        self.timeouts: list[int] = []

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.timeouts.append(request.timeout_seconds)
        return ExecutionResult(TargetStatus.SUCCEEDED, "ok", None, 1)


@pytest.mark.parametrize("configured_timeout", [60, 300])
def test_worker_propagates_configured_execution_timeout(
    db: Session, configured_timeout: int
) -> None:
    create(db, [HOST_OK])
    executor = TimeoutCaptureExecutor()
    settings = Settings(execution_timeout_seconds=configured_timeout, _env_file=None)
    assert WorkerService(db, executor, settings).run_once()
    assert executor.timeouts == [configured_timeout]


def test_execution_timeout_keeps_300_second_maximum() -> None:
    with pytest.raises(ValueError):
        Settings(execution_timeout_seconds=301, _env_file=None)


def test_conditional_claim_prevents_duplicate(db: Session) -> None:
    task_id = create(db, [HOST_OK])
    first = OperationService(db).tasks.claim_next(utc_now())
    assert first is not None and first.id == task_id
    assert OperationService(db).tasks.claim_next(utc_now()) is None
