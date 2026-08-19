from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import EnvironmentLevel, TargetStatus, TaskStatus
from app.core.errors import ForbiddenError
from app.executors.base import BaseExecutor, ExecutionRequest, ExecutionResult
from app.models import AuditLog, Environment, Host, Service, ServiceDeployment, TaskLog
from app.schemas import OperationCreate
from app.services.operations import OperationService
from app.services.worker import WorkerService

ENV = "00000000-0000-0000-0000-000000000001"
SERVICE = "20000000-0000-0000-0000-000000000001"
OTHER_SERVICE = "20000000-0000-0000-0000-000000000002"
HOST_OK = "10000000-0000-0000-0000-000000000001"
HOST_FAIL = "10000000-0000-0000-0000-000000000002"
FIXTURE_DIR = Path(__file__).parent / "fixtures"


def integration_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment_mode": "integration-test",
        "executor_type": "local_services",
        "write_operations_enabled": False,
        "production_operations_enabled": False,
        "dry_run_only": False,
        "execution_acknowledged": True,
        "allowed_environments": "test-mock",
        "allowed_hosts": "mock-host-ok,mock-host-fail",
        "allowed_services": "mock-service",
        "allowed_actions": "status",
        "services_script_path": str(FIXTURE_DIR / "fake_services.sh"),
        "services_working_directory": str(FIXTURE_DIR),
        "services_command_profile": "test-fixture-v1",
    }
    values.update(overrides)
    return Settings(**values)


def test_mode_gate_requires_acknowledgement_and_production_fails_closed() -> None:
    assert Settings().environment_mode == "mock"
    with pytest.raises(PydanticValidationError, match="OPSPILOT_EXECUTION_ACKNOWLEDGED"):
        integration_settings(execution_acknowledged=False)
    with pytest.raises(PydanticValidationError, match="Wildcards"):
        integration_settings(allowed_hosts="*")
    production = Settings(environment_mode="production")
    assert not production.write_operations_enabled
    assert not production.production_operations_enabled
    with pytest.raises(PydanticValidationError, match="forbids self approval"):
        Settings(environment_mode="production", allow_self_approval=True)


def test_integration_allowlists_reject_before_task_creation(db: Session) -> None:
    with pytest.raises(ForbiddenError) as service_rejection:
        OperationService(db, integration_settings()).create(
            OperationCreate(
                environment_id=ENV,
                action="status",
                scope="service",
                service_id=OTHER_SERVICE,
            )
        )
    assert service_rejection.value.code == "SERVICE_NOT_ALLOWED"

    with pytest.raises(ForbiddenError) as host_rejection:
        OperationService(
            db,
            integration_settings(allowed_hosts="mock-host-ok"),
        ).create(
            OperationCreate(
                environment_id=ENV,
                action="status",
                scope="service_hosts",
                service_id=SERVICE,
                host_ids=[HOST_FAIL],
            )
        )
    assert host_rejection.value.code == "HOST_NOT_ALLOWED"


def test_production_catalog_environment_allows_read_only_status(db: Session) -> None:
    environment = Environment(
        name="生产测试占位",
        code="production",
        enabled=True,
        environment_level=EnvironmentLevel.PRODUCTION,
    )
    host = Host(name="placeholder-host", environment=environment)
    service = Service(
        name="placeholder-service",
        service_type="application",
        environment=environment,
    )
    db.add_all([environment, host, service])
    db.flush()
    db.add(ServiceDeployment(service=service, host=host))
    db.commit()
    configured = integration_settings(
        allowed_environments="production",
        allowed_hosts="placeholder-host",
        allowed_services="placeholder-service",
    )
    task = OperationService(db, configured).create(
        OperationCreate(
            environment_id=environment.id,
            action="status",
            scope="service",
            service_id=service.id,
        )
    )
    assert task.action.value == "status"


class MixedIntegrationExecutor(BaseExecutor):
    executor_type = "test_mixed"

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.host_name == "mock-host-ok":
            return ExecutionResult(
                status=TargetStatus.SUCCEEDED,
                output='{"state":"running"}',
                error_message=None,
                duration_ms=21,
                exit_code=0,
                dry_run=False,
                service_state="RUNNING",
            )
        return ExecutionResult(
            status=TargetStatus.FAILED,
            output="",
            error_message="UNREACHABLE: reserved test address",
            duration_ms=42,
            exit_code=4,
            dry_run=False,
        )


def test_partial_result_logs_and_audit_evidence_are_persisted(db: Session) -> None:
    configured = integration_settings()
    task = OperationService(db, configured).create(
        OperationCreate(
            environment_id=ENV,
            action="status",
            scope="service_hosts",
            service_id=SERVICE,
            host_ids=[HOST_OK, HOST_FAIL],
        ),
        request_id="integration-request-id",
    )
    assert WorkerService(db, MixedIntegrationExecutor(), configured).run_once()
    db.refresh(task)
    assert task.status is TaskStatus.PARTIALLY_SUCCEEDED
    assert {target.duration_ms for target in task.targets} == {21, 42}
    logs = list(db.scalars(select(TaskLog).where(TaskLog.task_id == task.id)))
    assert len(logs) == 4
    assert {log.stream for log in logs} == {"stdout", "stderr"}
    assert {log.exit_code for log in logs} == {0, 4}
    assert not any(log.dry_run for log in logs)
    audits = list(
        db.scalars(
            select(AuditLog).where(AuditLog.task_id == task.id).order_by(AuditLog.created_at)
        )
    )
    assert audits[0].details["request_id"] == "integration-request-id"
    assert audits[0].details["environment"] == "test-mock"
    assert audits[-1].details["action"] == "status"
    assert audits[-1].details["result"] == "PARTIALLY_SUCCEEDED"


class ForbiddenExecutor(BaseExecutor):
    executor_type = "forbidden"

    def _execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise AssertionError(f"executor must not run for {request.action}")


def test_worker_rechecks_policy_before_executor_invocation(db: Session) -> None:
    task = OperationService(db, integration_settings()).create(
        OperationCreate(
            environment_id=ENV,
            action="status",
            scope="service_hosts",
            service_id=SERVICE,
            host_ids=[HOST_OK],
        )
    )
    target = task.targets[0]
    target.host.name = "changed-after-creation"
    db.commit()

    assert WorkerService(db, ForbiddenExecutor(), integration_settings()).run_once()
    db.refresh(task)
    assert task.status is TaskStatus.FAILED
    assert task.error_message and "HOST_NOT_ALLOWED" in task.error_message
    rejected = db.scalar(
        select(AuditLog).where(
            AuditLog.task_id == task.id,
            AuditLog.event_type == "EXECUTION_REJECTED",
        )
    )
    assert rejected is not None
    assert rejected.details["error_code"] == "HOST_NOT_ALLOWED"
