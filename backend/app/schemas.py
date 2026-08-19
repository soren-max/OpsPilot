from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import (
    ApprovalStatus,
    EnvironmentLevel,
    OperationAction,
    OperationScope,
    PartialFailurePolicy,
    TargetStatus,
    TaskStatus,
)


class EnvironmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    code: str
    enabled: bool
    description: str | None
    environment_level: EnvironmentLevel


class HostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    environment_id: str
    name: str
    description: str | None
    enabled: bool
    last_status: str
    service_count: int = 0


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    environment_id: str
    name: str
    service_type: str
    is_middleware: bool
    description: str | None
    enabled: bool
    host_count: int = 0
    current_status: str = "UNKNOWN"


class OperationCreate(BaseModel):
    environment_id: str = Field(min_length=36, max_length=36)
    action: OperationAction
    scope: OperationScope
    service_id: str | None = Field(default=None, min_length=36, max_length=36)
    host_id: str | None = Field(default=None, min_length=36, max_length=36)
    host_ids: list[str] = Field(default_factory=list, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)
    partial_failure_policy: PartialFailurePolicy | None = None
    requested_by: str = Field(
        default="web-user", min_length=1, max_length=80, pattern=r"^[\w .@-]+$"
    )

    @field_validator("host_ids")
    @classmethod
    def unique_host_ids(cls, value: list[str]) -> list[str]:
        if any(len(item) != 36 for item in value):
            raise ValueError("host_ids must contain UUID strings")
        if len(value) != len(set(value)):
            raise ValueError("host_ids must be unique")
        return value


class OperationCreated(BaseModel):
    task_id: str
    status: TaskStatus


class OperationRequestCreate(BaseModel):
    operation: OperationCreate
    reason: str = Field(min_length=3, max_length=1000)


class ApprovalDecisionCreate(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class ApprovalRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    approver_id: str
    decision: ApprovalStatus
    comment: str | None
    created_at: datetime


class OperationRequestRead(BaseModel):
    id: str
    requested_by: str
    action: OperationAction
    payload: dict[str, Any]
    status: ApprovalStatus
    task_id: str | None
    reason: str | None
    created_at: datetime
    updated_at: datetime
    approvals: list[ApprovalRecordRead] = Field(default_factory=list)


class TargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    host_id: str
    service_name: str
    host_name: str
    status: TargetStatus
    output: str | None
    error_message: str | None
    duration_ms: int | None
    attempt_count: int
    verification_status: TargetStatus | None
    verification_output: str | None


class TaskRead(BaseModel):
    id: str
    environment_id: str
    environment_name: str
    action: OperationAction
    scope: OperationScope
    status: TaskStatus
    requested_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    targets: list[TargetRead] = Field(default_factory=list)


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str | None
    event_type: str
    actor: str
    message: str
    details: dict[str, Any]
    created_at: datetime


class TaskLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    target_id: str | None
    stream: str
    message: str
    exit_code: int | None
    dry_run: bool
    created_at: datetime


class ServiceStatusSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    environment_id: str
    service_id: str
    host_id: str
    status: TargetStatus
    task_id: str
    observed_at: datetime
    dry_run: bool


class TopologySyncStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    environment_id: str
    last_task_id: str | None
    status: TaskStatus
    last_success_at: datetime | None
    error_message: str | None
    updated_at: datetime
