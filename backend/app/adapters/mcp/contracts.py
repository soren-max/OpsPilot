from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

MCP_PROTOCOL_VERSION = "2026-07-28"
CONTRACT_VERSION = "1"


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TimeBoundQuery(StrictContract):
    service: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    environment: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    start: datetime
    end: datetime


class MetricsToolInput(TimeBoundQuery):
    metric_kind: str = Field(min_length=1, max_length=40)
    step_seconds: int = Field(default=60, ge=15, le=3600)


class LogsToolInput(TimeBoundQuery):
    severity: str | None = Field(default=None, max_length=20)
    keywords: tuple[str, ...] = Field(default=(), max_length=5)
    limit: int = Field(default=20, ge=1, le=100)


class TicketsToolInput(TimeBoundQuery):
    status: str | None = Field(default=None, max_length=40)
    keywords: tuple[str, ...] = Field(default=(), max_length=5)
    limit: int = Field(default=10, ge=1, le=20)


class HealthToolInput(StrictContract):
    service: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    environment: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")


class KnowledgeToolInput(StrictContract):
    service: str = Field(min_length=1, max_length=120)
    environment: str = Field(min_length=1, max_length=80)
    symptoms: tuple[str, ...] = Field(max_length=5)
    evidence_summary: tuple[str, ...] = Field(default=(), max_length=10)
    severity: str | None = Field(default=None, max_length=20)
    tags: tuple[str, ...] = Field(default=(), max_length=10)
    limit: int = Field(default=5, ge=1, le=10)


class RemediationToolInput(StrictContract):
    incident_id: str = Field(min_length=1, max_length=64)
    action_type: str = Field(pattern="^restart_service$")
    target: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=1000)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=20)


class McpTrustLevel(StrEnum):
    LOCAL_TRUSTED = "LOCAL_TRUSTED"
    INTERNAL_TRUSTED = "INTERNAL_TRUSTED"
    EXTERNAL_UNTRUSTED = "EXTERNAL_UNTRUSTED"


class McpServerTrust(StrictContract):
    server_name: str = Field(min_length=1, max_length=120)
    level: McpTrustLevel


class RequestRiskContext(StrictContract):
    consumed_private_context: bool = False
    consumed_untrusted_external_data: bool = False
    attempted_mutation: bool = False


class ToolEnvelope(StrictContract):
    schema_version: str = CONTRACT_VERSION
    capability: str
    provenance: str
    data: object


class RemediationProposalResult(StrictContract):
    schema_version: str = CONTRACT_VERSION
    status: str
    risk_level: str
    approval_required: bool
    approval_id: str | None = None
    workflow_id: str | None = None
