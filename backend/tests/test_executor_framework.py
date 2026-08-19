from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import OperationAction, TargetStatus
from app.executors.base import ExecutionRequest, ExecutionTarget
from app.executors.command_builders.services_command import ServicesCommandBuilder
from app.executors.mock import MockExecutor
from app.executors.transports import TransportResult
from app.models import ServiceStatusSnapshot, TaskLog
from app.parsers import StructuredJsonParser
from app.schemas import OperationCreate
from app.services.operations import OperationService
from app.services.worker import WorkerService

ENV = "00000000-0000-0000-0000-000000000001"
SERVICE = "20000000-0000-0000-0000-000000000001"
HOST_OK = "10000000-0000-0000-0000-000000000001"


def test_local_executor_builds_argv_without_shell_execution() -> None:
    argv = ServicesCommandBuilder("/approved/fake_services.sh", "test-fixture-v1").build(
        ExecutionRequest(OperationAction.STATUS, "demo", "service-a", "host-a")
    )
    assert argv == [
        "/approved/fake_services.sh",
        "status",
        "demo",
        "host-a",
        "service-a",
    ]


def test_structured_parser_preserves_dry_run_result() -> None:
    result = StructuredJsonParser().parse(
        ExecutionRequest(OperationAction.STATUS, "demo", "service-a", "host-a"),
        TransportResult('{"status":"SUCCEEDED","message":"SIMULATED"}', "", 0, 1, "fixture"),
    )
    assert result.status is TargetStatus.SUCCEEDED
    assert result.dry_run


def test_public_executor_contract_is_transport_neutral() -> None:
    result = MockExecutor().execute(
        OperationAction.STATUS,
        ExecutionTarget("demo", "service-a", "host-a"),
        {"task_id": "task-1", "parameters": {"detail": True}},
    )
    assert result.success
    assert result.stdout
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.duration >= 0
    assert result.executor_type == "mock"
    assert set(result.as_dict()) == {
        "success",
        "stdout",
        "stderr",
        "exit_code",
        "duration_ms",
        "executor_type",
        "target_summary",
        "error_code",
        "timed_out",
        "execution_mode",
        "retryable",
    }


def test_worker_persists_task_log_and_status_snapshot(db: Session) -> None:
    task = OperationService(db).create(
        OperationCreate(
            environment_id=ENV,
            action="status",
            scope="service_hosts",
            service_id=SERVICE,
            host_ids=[HOST_OK],
        )
    )
    assert WorkerService(db, MockExecutor()).run_once()
    log = db.scalar(select(TaskLog).where(TaskLog.task_id == task.id))
    snapshot = db.scalar(
        select(ServiceStatusSnapshot).where(ServiceStatusSnapshot.environment_id == ENV)
    )
    assert log is not None and log.dry_run and log.exit_code == 0
    assert snapshot is not None and snapshot.task_id == task.id and snapshot.dry_run
