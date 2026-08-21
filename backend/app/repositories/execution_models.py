from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime
from app.domain.execution import BackendType, ExecutionStatus
from app.models import uuid_str


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    INDETERMINATE = "INDETERMINATE"


class ExecutionRecord(Base):
    __tablename__ = "execution_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    action_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    backend_type: Mapped[BackendType] = mapped_column(Enum(BackendType), index=True)
    backend_profile: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus), index=True)
    provider_execution_id: Mapped[str | None] = mapped_column(String(160), index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_reconciled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_category: Mapped[str | None] = mapped_column(String(80))
    safe_failure_message: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    safe_provider_status: Mapped[str | None] = mapped_column(String(80))
    verification_status: Mapped[str | None] = mapped_column(String(40))
    artifact_digest: Mapped[str | None] = mapped_column(String(160))
    git_commit_sha: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    __table_args__ = (
        UniqueConstraint("workflow_id", "action_fingerprint", name="uq_execution_workflow_action"),
    )


class ExecutionOutboxRecord(Base):
    __tablename__ = "execution_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    execution_id: Mapped[str] = mapped_column(
        ForeignKey("execution_records.id"), index=True, unique=True
    )
    message_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(Enum(OutboxStatus), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    claimed_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
