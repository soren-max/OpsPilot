from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

SAFE_TARGET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SAFE_SERVICE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}$")


class ActionType(StrEnum):
    GET_SERVICE_STATUS = "get_service_status"
    HEALTH_CHECK = "health_check"
    START_SERVICE = "start_service"
    STOP_SERVICE = "stop_service"
    RESTART_SERVICE = "restart_service"


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FORBIDDEN = "forbidden"


class TargetEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ActionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"


class StrictDomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ServiceActionParams(StrictDomainModel):
    service: Annotated[str, Field(min_length=1, max_length=128, pattern=SAFE_SERVICE.pattern)]


# Health actions carry semantic identity only. Endpoint, port and success criteria are
# operator-owned verification configuration rather than caller-controlled parameters.
HealthCheckParams = ServiceActionParams


ActionParameters = ServiceActionParams


class ActionRequest(StrictDomainModel):
    action_type: ActionType
    target: Annotated[str, Field(min_length=1, max_length=128, pattern=SAFE_TARGET.pattern)]
    environment: TargetEnvironment
    parameters: ActionParameters
    reason: Annotated[str, Field(min_length=3, max_length=1000)]

    @model_validator(mode="after")
    def parameters_match_action(self) -> ActionRequest:
        expected_type = {
            ActionType.GET_SERVICE_STATUS: ServiceActionParams,
            ActionType.START_SERVICE: ServiceActionParams,
            ActionType.STOP_SERVICE: ServiceActionParams,
            ActionType.RESTART_SERVICE: ServiceActionParams,
            ActionType.HEALTH_CHECK: ServiceActionParams,
        }[self.action_type]
        if not isinstance(self.parameters, expected_type):
            raise ValueError(
                f"{self.action_type.value} requires {expected_type.__name__}"
            )
        return self


class RiskAssessment(StrictDomainModel):
    risk_level: RiskLevel
    reason: str
    approval_required: bool
    policy_rule: str
    allowed: bool


class ActionPreview(StrictDomainModel):
    action_type: ActionType
    target: str
    executor: str
    operation: str
    changes_state: bool


class ActionResult(StrictDomainModel):
    action_type: ActionType
    target: str
    status: ActionStatus
    summary: str
    executor: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VerificationResult(StrictDomainModel):
    action_type: ActionType
    target: str
    status: ActionStatus
    verified: bool
    summary: str
