import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    ApprovalStatus,
    EnvironmentLevel,
    IntegrationConfigStatus,
    OperationAction,
    OperationScope,
    PartialFailurePolicy,
    TargetStatus,
    TaskStatus,
)
from app.db.base import Base, TimestampMixin, UTCDateTime


def uuid_str() -> str:
    return str(uuid.uuid4())


class Environment(TimestampMixin, Base):
    __tablename__ = "environments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    environment_level: Mapped[EnvironmentLevel] = mapped_column(
        Enum(EnvironmentLevel), default=EnvironmentLevel.DEVELOPMENT, nullable=False
    )


class Host(TimestampMixin, Base):
    __tablename__ = "hosts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mock_behavior: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    last_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN", nullable=False)
    address: Mapped[str | None] = mapped_column(String(253))
    ssh_port: Mapped[int | None] = mapped_column(Integer)
    ssh_username: Mapped[str | None] = mapped_column(String(64))
    credential_reference: Mapped[str | None] = mapped_column(String(80))
    environment: Mapped[Environment] = relationship()
    deployments: Mapped[list["ServiceDeployment"]] = relationship(back_populates="host")
    __table_args__ = (UniqueConstraint("environment_id", "name"),)


class Service(TimestampMixin, Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    service_type: Mapped[str] = mapped_column(String(40), nullable=False)
    is_middleware: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    environment: Mapped[Environment] = relationship()
    deployments: Mapped[list["ServiceDeployment"]] = relationship(back_populates="service")
    __table_args__ = (UniqueConstraint("environment_id", "name"),)


class ServiceDeployment(TimestampMixin, Base):
    __tablename__ = "service_deployments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("hosts.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    service: Mapped[Service] = relationship(back_populates="deployments")
    host: Mapped[Host] = relationship(back_populates="deployments")
    __table_args__ = (UniqueConstraint("service_id", "host_id"),)


class OperationsIntegrationConfig(TimestampMixin, Base):
    __tablename__ = "operations_integration_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    environment_id: Mapped[str] = mapped_column(
        ForeignKey("environments.id"), unique=True, index=True, nullable=False
    )
    status: Mapped[IntegrationConfigStatus] = mapped_column(
        Enum(IntegrationConfigStatus), default=IntegrationConfigStatus.DRAFT, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remote_services_path: Mapped[str] = mapped_column(String(512), nullable=False)
    remote_working_directory: Mapped[str] = mapped_column(String(512), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    status_argv: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    start_argv: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    stop_argv: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    parser_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    allowlist: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    validation_errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_ssh_test_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_status_test_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_test_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    environment: Mapped[Environment] = relationship()


class OperationTask(TimestampMixin, Base):
    __tablename__ = "operation_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    action: Mapped[OperationAction] = mapped_column(Enum(OperationAction), nullable=False)
    scope: Mapped[OperationScope] = mapped_column(Enum(OperationScope), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, index=True, nullable=False
    )
    requested_by: Mapped[str] = mapped_column(String(80), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_message: Mapped[str | None] = mapped_column(Text)
    operation_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("operation_requests.id"), index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    partial_failure_policy: Mapped[PartialFailurePolicy] = mapped_column(
        Enum(PartialFailurePolicy), default=PartialFailurePolicy.NONE, nullable=False
    )
    targets: Mapped[list["OperationTarget"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    __table_args__ = (
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_operation_tasks_requested_by_idempotency_key",
        ),
    )


class OperationTarget(TimestampMixin, Base):
    __tablename__ = "operation_targets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    task_id: Mapped[str] = mapped_column(ForeignKey("operation_tasks.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("hosts.id"), index=True)
    status: Mapped[TargetStatus] = mapped_column(
        Enum(TargetStatus), default=TargetStatus.PENDING, nullable=False
    )
    output: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None]
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    verification_status: Mapped[TargetStatus | None] = mapped_column(Enum(TargetStatus))
    verification_output: Mapped[str | None] = mapped_column(Text)
    task: Mapped[OperationTask] = relationship(back_populates="targets")
    service: Mapped[Service] = relationship()
    host: Mapped[Host] = relationship()
    __table_args__ = (UniqueConstraint("task_id", "service_id", "host_id"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


@event.listens_for(AuditLog, "before_update")
@event.listens_for(AuditLog, "before_delete")
def prevent_audit_mutation(_mapper: object, _connection: object, _audit: AuditLog) -> None:
    raise ValueError("AuditLog is append-only through the application data layer")


class TaskLog(Base):
    __tablename__ = "task_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    task_id: Mapped[str] = mapped_column(ForeignKey("operation_tasks.id"), index=True)
    target_id: Mapped[str | None] = mapped_column(ForeignKey("operation_targets.id"), index=True)
    stream: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int | None]
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class ServiceStatusSnapshot(Base):
    __tablename__ = "service_status_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("hosts.id"), index=True)
    status: Mapped[TargetStatus] = mapped_column(Enum(TargetStatus), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("operation_tasks.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("environment_id", "service_id", "host_id"),)


class TopologySyncState(Base):
    __tablename__ = "topology_sync_states"
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), primary_key=True)
    last_task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"))
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False
    )
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Historic migrated accounts may have no local credential. They cannot log in
    # until an administrator explicitly sets a password; no password is invented.
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    auth_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


@event.listens_for(User, "before_update")
def invalidate_user_tokens_on_auth_change(_mapper: object, _connection: object, user: User) -> None:
    state = inspect(user)
    if any(
        state.attrs[field].history.has_changes() for field in ("password_hash", "enabled", "status")
    ):
        user.auth_version += 1


class Role(TimestampMixin, Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), primary_key=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("permissions.id"), primary_key=True)


class OperationRequest(TimestampMixin, Base):
    __tablename__ = "operation_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[OperationAction] = mapped_column(Enum(OperationAction), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False
    )
    # Logical reference only; the task owns the FK to avoid a circular schema dependency.
    task_id: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    approval_records: Mapped[list["ApprovalRecord"]] = relationship(
        back_populates="operation_request", cascade="all, delete-orphan"
    )
    __table_args__ = (
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_operation_requests_requested_by_idempotency_key",
        ),
    )


class ApprovalRecord(Base):
    __tablename__ = "approval_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    operation_request_id: Mapped[str] = mapped_column(
        ForeignKey("operation_requests.id"), index=True
    )
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    operation_request: Mapped[OperationRequest] = relationship(back_populates="approval_records")
    __table_args__ = (
        UniqueConstraint(
            "operation_request_id",
            "approver_id",
            name="uq_approval_records_operation_request_id_approver_id",
        ),
    )


class OperationLock(Base):
    __tablename__ = "operation_locks"
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), primary_key=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("hosts.id"), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("operation_tasks.id"), index=True)
    acquired_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
