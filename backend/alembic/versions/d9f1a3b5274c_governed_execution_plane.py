"""add governed execution records and transactional outbox

Revision ID: d9f1a3b5274c
Revises: c8e0f2a4163b
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9f1a3b5274c"
down_revision: str | None = "c8e0f2a4163b"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for value in (
            "EXECUTION_ROUTED",
            "EXECUTION_QUEUED",
            "EXECUTION_DISPATCHED",
            "EXECUTION_SUBMITTED",
            "EXECUTION_RECONCILED",
            "EXECUTION_SUCCEEDED",
            "EXECUTION_FAILED",
            "EXECUTION_UNKNOWN",
            "EXECUTION_VERIFICATION_FAILED",
        ):
            op.execute(f"ALTER TYPE auditeventtype ADD VALUE IF NOT EXISTS '{value}'")
    backend_type = sa.Enum("MOCK", "ANSIBLE", "HARNESS", name="backendtype")
    execution_status = sa.Enum(
        "PLANNED",
        "APPROVED",
        "QUEUED",
        "DISPATCHING",
        "SUBMITTED",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "UNKNOWN",
        "RECONCILIATION_REQUIRED",
        name="executionstatus",
    )
    outbox_status = sa.Enum("PENDING", "CLAIMED", "COMPLETED", "INDETERMINATE", name="outboxstatus")
    op.create_table(
        "execution_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("action_fingerprint", sa.String(64), nullable=False),
        sa.Column("backend_type", backend_type, nullable=False),
        sa.Column("backend_profile", sa.String(120), nullable=False),
        sa.Column("status", execution_status, nullable=False),
        sa.Column("provider_execution_id", sa.String(160)),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True)),
        sa.Column("failure_category", sa.String(80)),
        sa.Column("safe_failure_message", sa.Text()),
        sa.Column("trace_id", sa.String(32)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("safe_provider_status", sa.String(80)),
        sa.Column("verification_status", sa.String(40)),
        sa.Column("artifact_digest", sa.String(160)),
        sa.Column("git_commit_sha", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"]),
        sa.UniqueConstraint(
            "workflow_id", "action_fingerprint", name="uq_execution_workflow_action"
        ),
    )
    for field in ("incident_id", "workflow_id", "backend_type", "status", "provider_execution_id"):
        op.create_index(f"ix_execution_records_{field}", "execution_records", [field])
    op.create_table(
        "execution_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_id", sa.String(36), nullable=False, unique=True),
        sa.Column("message_type", sa.String(80), nullable=False),
        sa.Column("payload_reference", sa.String(160), nullable=False),
        sa.Column("status", outbox_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_until", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["execution_records.id"]),
    )
    for field in ("execution_id", "status", "available_at", "claimed_until"):
        op.create_index(f"ix_execution_outbox_{field}", "execution_outbox", [field])


def downgrade() -> None:
    op.drop_table("execution_outbox")
    op.drop_table("execution_records")
    if op.get_bind().dialect.name != "postgresql":
        sa.Enum(name="outboxstatus").drop(op.get_bind(), checkfirst=True)
        sa.Enum(name="executionstatus").drop(op.get_bind(), checkfirst=True)
        sa.Enum(name="backendtype").drop(op.get_bind(), checkfirst=True)
