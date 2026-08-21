"""add durable human approval requests

Revision ID: c8e0f2a4163b
Revises: b7d9f1a3052e
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e0f2a4163b"
down_revision: str | None = "b7d9f1a3052e"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE auditeventtype ADD VALUE IF NOT EXISTS 'APPROVAL_APPROVED'")
        op.execute("ALTER TYPE auditeventtype ADD VALUE IF NOT EXISTS 'WORKFLOW_RESUMED'")
    approval_status = sa.Enum(
        "PENDING", "APPROVED", "REJECTED", "EXPIRED", name="approvalstatus"
    )
    approval_decision = sa.Enum("APPROVE", "REJECT", name="approvaldecision")
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("workflow_run_id", sa.String(36), nullable=False),
        sa.Column("action_request_id", sa.String(64), nullable=False),
        sa.Column("action_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", approval_status, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("approver_identity", sa.String(80)),
        sa.Column("approver_display_name", sa.String(120)),
        sa.Column("approver_type", sa.String(32)),
        sa.Column("decision", approval_decision),
        sa.Column("reason", sa.Text()),
        sa.Column("resumed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"]),
        sa.UniqueConstraint(
            "workflow_run_id", "action_fingerprint", name="uq_approval_workflow_action"
        ),
    )
    op.create_index("ix_approval_requests_incident_id", "approval_requests", ["incident_id"])
    op.create_index(
        "ix_approval_requests_workflow_run_id", "approval_requests", ["workflow_run_id"]
    )
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_workflow_run_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_incident_id", table_name="approval_requests")
    op.drop_table("approval_requests")
    if op.get_bind().dialect.name != "postgresql":
        sa.Enum(name="approvaldecision").drop(op.get_bind(), checkfirst=True)
        sa.Enum(name="approvalstatus").drop(op.get_bind(), checkfirst=True)
