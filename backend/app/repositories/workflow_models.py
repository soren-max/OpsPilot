from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime
from app.models import uuid_str


class WorkflowRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowRunRecord(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    graph_name: Mapped[str] = mapped_column(String(80), nullable=False)
    graph_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[WorkflowRunStatus] = mapped_column(Enum(WorkflowRunStatus), index=True)
    started_by: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    current_node: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_checkpoint_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(Text)
    hypothesis_id: Mapped[str | None] = mapped_column(String(36))
    diagnosis_id: Mapped[str | None] = mapped_column(String(36))
    proposed_action_id: Mapped[str | None] = mapped_column(String(64))
    execution_task_id: Mapped[str | None] = mapped_column(String(64))
    state_references: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "incident_id", "started_by", "idempotency_key",
            name="uq_workflow_run_incident_actor_idempotency",
        ),
    )


class WorkflowEvaluationRecord(Base):
    __tablename__ = "workflow_evaluation_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    expected_outcome: Mapped[str] = mapped_column(String(500), nullable=False)
    actual_outcome: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
