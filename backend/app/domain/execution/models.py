from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.actions.models import ActionType, RiskLevel, TargetEnvironment


class StrictExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BackendType(StrEnum):
    MOCK = "mock"
    ANSIBLE = "ansible"
    HARNESS = "harness"


class ExecutionMode(StrEnum):
    REMEDIATE = "REMEDIATE"
    CHANGE = "CHANGE"


class ExecutionStatus(StrEnum):
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    DISPATCHING = "DISPATCHING"
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class ExecutionBackendDescriptor(StrictExecutionModel):
    backend_type: BackendType
    supported_action_types: frozenset[ActionType]
    supported_modes: frozenset[ExecutionMode]
    supported_environments: frozenset[TargetEnvironment]
    supports_async: bool
    supports_status: bool
    supports_cancel: bool
    supports_reconciliation: bool
    max_risk_level: RiskLevel


class ExecutionProfile(StrictExecutionModel):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    backend_type: BackendType
    environment: TargetEnvironment
    allowed_action_types: frozenset[ActionType]
    target_mapping: dict[str, str] = Field(default_factory=dict)
    immutable_refs: dict[str, str] = Field(default_factory=dict)
    rollback_profile: str | None = Field(default=None, max_length=120)


class ExecutionRoute(StrictExecutionModel):
    backend_type: BackendType
    profile_name: str
    mode: ExecutionMode


class ExecutionContext(StrictExecutionModel):
    execution_id: str
    incident_id: str
    workflow_id: str
    profile: ExecutionProfile
    trace_id: str | None = None


class ExecutionPreview(StrictExecutionModel):
    backend_type: BackendType
    profile_name: str
    operation: str
    changes_state: bool


class ExecutionSubmission(StrictExecutionModel):
    execution_id: str
    backend_type: BackendType
    backend_execution_id: str | None
    submitted_at: datetime
    initial_status: ExecutionStatus
    safe_provider_status: str | None = Field(default=None, max_length=80)


class ReconciliationResult(StrictExecutionModel):
    execution_id: str
    status: ExecutionStatus
    reconciled_at: datetime
    backend_execution_id: str | None = None
    safe_provider_status: str | None = Field(default=None, max_length=80)
    safe_message: str | None = Field(default=None, max_length=500)


class CompensationPlan(StrictExecutionModel):
    failed_execution_id: str
    rollback_profile: str
    reason: str = Field(min_length=3, max_length=500)
    requires_policy_and_approval: bool = True
