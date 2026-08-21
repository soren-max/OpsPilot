from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ApprovalActorType(StrEnum):
    HUMAN = "HUMAN"
    SERVICE = "SERVICE"


class ApprovalActor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    actor_type: ApprovalActorType = ApprovalActorType.HUMAN


class ApprovalResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: ApprovalDecision
    actor: ApprovalActor
    reason: str = Field(min_length=1, max_length=1000)
    resolved_at: datetime
