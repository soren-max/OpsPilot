import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.command_profiles import CommandAction, CommandProfile
from app.core.config import Settings
from app.core.enums import EnvironmentLevel
from app.core.errors import ForbiddenError
from app.models import AuditLog, Environment, Host, OperationTask, Service, User
from app.schemas import OperationCreate
from app.services.operations import OperationService

ENV = "00000000-0000-0000-0000-000000000001"
SERVICE = "20000000-0000-0000-0000-000000000001"
HOST = "10000000-0000-0000-0000-000000000001"


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "allowed_environments": "test-mock",
        "allowed_hosts": "mock-host-ok",
        "allowed_services": "mock-service",
        "allowed_actions": "status",
        "write_operations_enabled": False,
        "approval_required_for_write": True,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def create(db: Session, configured: Settings, action: str = "status") -> object:
    return OperationService(db, configured).create(
        OperationCreate(
            environment_id=ENV,
            action=action,
            scope="service_hosts",
            service_id=SERVICE,
            host_ids=[HOST],
        )
    )


def test_allowlisted_status_can_create_task(db: Session) -> None:
    assert create(db, settings()).action.value == "status"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("allowed_environments", "ENVIRONMENT_NOT_ALLOWED"),
        ("allowed_hosts", "HOST_NOT_ALLOWED"),
        ("allowed_services", "SERVICE_NOT_ALLOWED"),
        ("allowed_actions", "ACTION_NOT_ALLOWED"),
    ],
)
def test_empty_allowlists_fail_closed(db: Session, field: str, code: str) -> None:
    with pytest.raises(ForbiddenError) as raised:
        create(db, settings(**{field: ""}))
    assert raised.value.code == code


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("allowed_environments", "other", "ENVIRONMENT_NOT_ALLOWED"),
        ("allowed_hosts", "other", "HOST_NOT_ALLOWED"),
        ("allowed_services", "other", "SERVICE_NOT_ALLOWED"),
        ("allowed_actions", "", "ACTION_NOT_ALLOWED"),
    ],
)
def test_allowlists_fail_closed(db: Session, field: str, value: str, code: str) -> None:
    with pytest.raises(ForbiddenError) as raised:
        create(db, settings(**{field: value}))
    assert raised.value.code == code
    assert db.scalar(select(func.count()).select_from(OperationTask)) == 0


@pytest.mark.parametrize("action", ["start", "stop", "restart", "deploy"])
def test_write_actions_return_403_audit_and_create_no_task(db: Session, action: str) -> None:
    with pytest.raises(ForbiddenError) as raised:
        create(db, settings(), action)
    assert raised.value.status_code == 403
    assert raised.value.code == "WRITE_OPERATION_DISABLED"
    assert db.scalar(select(func.count()).select_from(OperationTask)) == 0
    audit = db.scalar(select(AuditLog).where(AuditLog.event_type == "EXECUTION_REJECTED"))
    assert audit is not None
    assert audit.details["error_code"] == "WRITE_OPERATION_DISABLED"
    assert audit.task_id is None


def test_permission_rejection_is_audited_with_requested_target_context(
    db: Session,
) -> None:
    actor = User(
        username="read-only-user",
        display_name="Read only",
        password_hash="not-a-real-credential",
    )
    db.add(actor)
    db.commit()
    with pytest.raises(ForbiddenError) as raised:
        OperationService(db, settings()).create(
            OperationCreate(
                environment_id=ENV,
                action="start",
                scope="service_hosts",
                service_id=SERVICE,
                host_ids=[HOST],
            ),
            actor=actor,
        )
    assert raised.value.code == "PERMISSION_DENIED"
    audit = db.scalar(select(AuditLog).where(AuditLog.event_type == "EXECUTION_REJECTED"))
    assert audit is not None
    assert audit.actor.startswith("account-")
    assert audit.details["environment"] == "test-mock"
    assert len(audit.details["hosts"]) == 1
    assert audit.details["hosts"][0].startswith("host-")
    assert audit.details["service"] == "mock-service"
    assert audit.details["action"] == "start"
    assert db.scalar(select(func.count()).select_from(OperationTask)) == 0


def test_start_stop_paths_cannot_bypass_gate(db: Session) -> None:
    configured = settings(
        services_start_script_path="/tmp/start.sh",
        services_stop_script_path="/tmp/stop.sh",
    )
    with pytest.raises(ForbiddenError) as raised:
        create(db, configured, "start")
    assert raised.value.code == "WRITE_OPERATION_DISABLED"


@pytest.mark.parametrize("action", ["start", "stop"])
def test_write_action_in_allowlist_still_cannot_bypass_closed_write_switch(
    db: Session, action: str
) -> None:
    configured = settings(allowed_actions=f"status,{action}")
    with pytest.raises(ForbiddenError) as raised:
        create(db, configured, action)
    assert raised.value.code == "WRITE_OPERATION_DISABLED"
    assert db.scalar(select(func.count()).select_from(OperationTask)) == 0


@pytest.mark.parametrize("action", ["start", "stop"])
def test_real_status_only_mode_rejects_profile_write_capabilities(db: Session, action: str) -> None:
    profile = CommandProfile(
        capabilities=["status", "start", "stop"],
        parser="json_status",
        actions={
            item: CommandAction(argv=[item, "{environment}", "{host}", "{service}"])
            for item in ("status", "start", "stop")
        },
    )
    configured = settings(
        environment_mode="integration-test",
        executor_type="local_services",
        dry_run_only=False,
        execution_acknowledged=True,
        write_operations_enabled=False,
        production_operations_enabled=False,
        services_script_path="/confirmed/services.sh",
        services_working_directory="/confirmed",
        services_command_profile="confirmed-v1",
        command_profiles={"confirmed-v1": profile},
        allowed_actions="status",
    )
    assert create(db, configured, "status").action.value == "status"  # type: ignore[union-attr]
    with pytest.raises(ForbiddenError) as raised:
        create(db, configured, action)
    assert raised.value.code == "WRITE_OPERATION_DISABLED"


def test_open_write_switch_cannot_bypass_action_allowlist(db: Session) -> None:
    configured = settings(
        write_operations_enabled=True,
        approval_required_for_write=False,
        allowed_actions="status",
    )
    with pytest.raises(ForbiddenError) as raised:
        create(db, configured, "start")
    assert raised.value.code == "ACTION_NOT_ALLOWED"
    assert db.scalar(select(func.count()).select_from(OperationTask)) == 0


def test_production_write_is_rejected_when_production_switch_is_closed(
    db: Session,
) -> None:
    environment = db.get(Environment, ENV)
    assert environment is not None
    environment.code = "prod-test"
    environment.environment_level = EnvironmentLevel.PRODUCTION
    db.commit()
    configured = settings(
        write_operations_enabled=True,
        production_operations_enabled=False,
        approval_required_for_write=False,
        allowed_environments="prod-test",
        allowed_actions="status,start",
    )
    with pytest.raises(ForbiddenError) as raised:
        create(db, configured, "start")
    assert raised.value.code == "PRODUCTION_OPERATION_DISABLED"


def test_production_switch_cannot_be_enabled_without_write_switch() -> None:
    with pytest.raises(ValueError, match="requires OPSPILOT_WRITE_OPERATIONS_ENABLED"):
        settings(production_operations_enabled=True)


def test_v1_3_0_accepts_production_writes_only_with_every_platform_gate(tmp_path) -> None:
    wrapper = tmp_path / "ssh-wrapper.sh"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    configured = settings(
        environment_mode="production",
        executor_type="local_services",
        dry_run_only=False,
        write_operations_enabled=True,
        production_operations_enabled=True,
        execution_acknowledged=True,
        approval_required_for_write=True,
        allow_self_approval=False,
        services_script_path=str(wrapper),
        services_working_directory=str(tmp_path),
        services_command_profile="pending-confirmation",
        allowed_environments="",
        allowed_hosts="",
        allowed_services="",
        allowed_actions="status,start,stop",
    )
    assert configured.production_operations_enabled is True
    assert configured.write_operations_enabled is True
    assert configured.execution_is_acknowledged is True


def test_configured_mock_write_can_create_task(db: Session) -> None:
    configured = settings(
        write_operations_enabled=True,
        production_operations_enabled=False,
        approval_required_for_write=False,
        allowed_actions="status,start",
    )
    task = create(db, configured, "start")
    assert task.action.value == "start"  # type: ignore[union-attr]
    assert db.scalar(select(func.count()).select_from(OperationTask)) == 1


def test_approval_requirement_blocks_direct_write(db: Session) -> None:
    configured = settings(
        write_operations_enabled=True,
        approval_required_for_write=True,
        allowed_actions="status,start",
    )
    with pytest.raises(ForbiddenError) as raised:
        create(db, configured, "start")
    assert raised.value.code == "APPROVAL_REQUIRED"


def test_unsafe_catalog_identifier_is_rejected(db: Session) -> None:
    host = db.get(Host, HOST)
    assert host is not None
    host.name = "host;id"
    db.commit()
    configured = settings(allowed_hosts="host;id")
    with pytest.raises(ForbiddenError) as raised:
        create(db, configured)
    assert raised.value.code == "UNSAFE_TARGET_IDENTIFIER"


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("host", "host|id"),
        ("host", "host>result"),
        ("service", "service`id`"),
        ("service", "service\nid"),
    ],
)
def test_command_injection_characters_are_rejected_after_allowlist(
    db: Session, field: str, unsafe_value: str
) -> None:
    host = db.get(Host, HOST)
    service = db.get(Service, SERVICE)
    assert host and service
    if field == "host":
        host.name = unsafe_value
    else:
        service.name = unsafe_value
    db.commit()
    configured = settings(
        allowed_hosts=host.name,
        allowed_services=service.name,
    )
    with pytest.raises(ForbiddenError) as raised:
        create(db, configured)
    assert raised.value.code == "UNSAFE_TARGET_IDENTIFIER"


def test_production_name_allows_read_only_status(db: Session) -> None:
    environment = db.get(Environment, ENV)
    host = db.get(Host, HOST)
    service = db.get(Service, SERVICE)
    assert environment and host and service
    environment.code = "production-like"
    environment.environment_level = EnvironmentLevel.TEST
    db.commit()
    configured = settings(
        allowed_environments="production-like",
        allowed_hosts=host.name,
        allowed_services=service.name,
    )
    task = create(db, configured)
    assert task.action.value == "status"  # type: ignore[union-attr]
