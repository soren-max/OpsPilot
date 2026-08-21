from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime
from app.domain.approvals import ApprovalDecision, ApprovalStatus
from app.models import uuid_str


class ApprovalRequestRecord(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    workflow_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    action_request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), index=True)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approver_identity: Mapped[str | None] = mapped_column(String(80))
    approver_display_name: Mapped[str | None] = mapped_column(String(120))
    approver_type: Mapped[str | None] = mapped_column(String(32))
    decision: Mapped[ApprovalDecision | None] = mapped_column(Enum(ApprovalDecision))
    reason: Mapped[str | None] = mapped_column(Text)
    resumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        UniqueConstraint(
            "workflow_run_id", "action_fingerprint", name="uq_approval_workflow_action"
        ),
    )
