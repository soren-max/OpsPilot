from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime
from app.domain.change import ChangeStatus, ChangeType
from app.models import uuid_str


class ChangeOutboxStatus(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    INDETERMINATE = "INDETERMINATE"


class ChangeRecord(Base):
    __tablename__ = "change_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    workflow_id: Mapped[str] = mapped_column(String(64), index=True)
    action_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(120), index=True)
    change_type: Mapped[ChangeType] = mapped_column(Enum(ChangeType), index=True)
    status: Mapped[ChangeStatus] = mapped_column(Enum(ChangeStatus), index=True)
    source_revision: Mapped[str | None] = mapped_column(String(64))
    branch: Mapped[str | None] = mapped_column(String(160), unique=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), index=True)
    pull_request_id: Mapped[str | None] = mapped_column(String(80), index=True)
    pull_request_url: Mapped[str | None] = mapped_column(String(1000))
    merged_revision: Mapped[str | None] = mapped_column(String(64), index=True)
    gitops_application_ref: Mapped[str] = mapped_column(String(160))
    policy_result_ref: Mapped[str | None] = mapped_column(String(64))
    approval_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    approval_actor: Mapped[str | None] = mapped_column(String(80))
    approval_reason: Mapped[str | None] = mapped_column(String(500))
    approval_decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verification_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    verification_status: Mapped[str | None] = mapped_column(String(40))
    sync_status: Mapped[str | None] = mapped_column(String(40))
    health_status: Mapped[str | None] = mapped_column(String(40))
    failure_category: Mapped[str | None] = mapped_column(String(80))
    safe_failure_message: Mapped[str | None] = mapped_column(Text)
    intent_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    profile_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_set_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    review_state: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (
        UniqueConstraint("workflow_id", "action_fingerprint", name="uq_change_workflow_action"),
    )


class ChangeOutboxRecord(Base):
    __tablename__ = "change_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_records.id"), index=True, unique=True)
    message_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[ChangeOutboxStatus] = mapped_column(Enum(ChangeOutboxStatus), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    claimed_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class GitEventInboxRecord(Base):
    __tablename__ = "git_event_inbox"
    delivery_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    repository_ref: Mapped[str] = mapped_column(String(240), index=True)
    change_id: Mapped[str | None] = mapped_column(ForeignKey("change_records.id"), index=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
