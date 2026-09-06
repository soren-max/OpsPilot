"""add governed GitOps change workflow

Revision ID: e0a2b4c6d8f0
Revises: d9f1a3b5274c
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e0a2b4c6d8f0"
down_revision: str | None = "d9f1a3b5274c"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


AUDIT_EVENTS = (
    "CHANGE_PROPOSED",
    "CHANGE_POLICY_ASSESSED",
    "CHANGE_APPROVAL_REQUESTED",
    "CHANGE_APPROVED",
    "CHANGE_PLANNED",
    "CHANGE_VALIDATED",
    "CHANGE_QUEUED",
    "GIT_BRANCH_CREATED",
    "GIT_COMMIT_CREATED",
    "PULL_REQUEST_CREATED",
    "PULL_REQUEST_REVIEWED",
    "PULL_REQUEST_MERGED",
    "GITOPS_RECONCILIATION_STARTED",
    "GITOPS_SYNCED",
    "GITOPS_HEALTHY",
    "CHANGE_VERIFICATION_FAILED",
    "CHANGE_VERIFIED",
    "CHANGE_RESOLVED",
    "CHANGE_RECONCILIATION_REQUIRED",
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for value in AUDIT_EVENTS:
            op.execute(f"ALTER TYPE auditeventtype ADD VALUE IF NOT EXISTS '{value}'")
    change_type = sa.Enum("ROLLBACK_IMAGE", "SCALE_REPLICAS", name="changetype")
    change_status = sa.Enum(
        "PROPOSED",
        "POLICY_APPROVED",
        "WAITING_APPROVAL",
        "APPROVED",
        "PLANNED",
        "VALIDATED",
        "QUEUED",
        "BRANCH_CREATED",
        "COMMITTED",
        "PR_CREATED",
        "WAITING_REVIEW",
        "APPROVED_FOR_MERGE",
        "MERGED",
        "RECONCILING",
        "SYNCED",
        "HEALTHY",
        "VERIFIED",
        "RESOLVED",
        "REJECTED",
        "FAILED",
        "UNKNOWN",
        "RECONCILIATION_REQUIRED",
        name="changestatus",
    )
    outbox_status = sa.Enum(
        "PENDING", "CLAIMED", "COMPLETED", "INDETERMINATE", name="changeoutboxstatus"
    )
    op.create_table(
        "change_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(64), nullable=False),
        sa.Column("action_fingerprint", sa.String(64), nullable=False),
        sa.Column("profile_id", sa.String(120), nullable=False),
        sa.Column("change_type", change_type, nullable=False),
        sa.Column("status", change_status, nullable=False),
        sa.Column("source_revision", sa.String(64)),
        sa.Column("branch", sa.String(160), unique=True),
        sa.Column("commit_sha", sa.String(64)),
        sa.Column("pull_request_id", sa.String(80)),
        sa.Column("pull_request_url", sa.String(1000)),
        sa.Column("merged_revision", sa.String(64)),
        sa.Column("gitops_application_ref", sa.String(160), nullable=False),
        sa.Column("policy_result_ref", sa.String(64)),
        sa.Column("approval_id", sa.String(36), unique=True),
        sa.Column("approval_actor", sa.String(80)),
        sa.Column("approval_reason", sa.String(500)),
        sa.Column("approval_decided_at", sa.DateTime(timezone=True)),
        sa.Column("verification_id", sa.String(36), unique=True),
        sa.Column("verification_status", sa.String(40)),
        sa.Column("gitops_revision", sa.String(length=64), nullable=True),
        sa.Column("sync_status", sa.String(40)),
        sa.Column("health_status", sa.String(40)),
        sa.Column("failure_category", sa.String(80)),
        sa.Column("safe_failure_message", sa.Text()),
        sa.Column("intent_payload", sa.JSON(), nullable=False),
        sa.Column("profile_payload", sa.JSON(), nullable=False),
        sa.Column("policy_payload", sa.JSON(), nullable=False),
        sa.Column("change_set_payload", sa.JSON()),
        sa.Column("review_state", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.UniqueConstraint("workflow_id", "action_fingerprint", name="uq_change_workflow_action"),
    )
    for field in (
        "incident_id",
        "workflow_id",
        "profile_id",
        "change_type",
        "status",
        "commit_sha",
        "pull_request_id",
        "merged_revision",
    ):
        op.create_index(f"ix_change_records_{field}", "change_records", [field])
    op.create_table(
        "change_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("change_id", sa.String(36), nullable=False, unique=True),
        sa.Column("message_type", sa.String(80), nullable=False),
        sa.Column("status", outbox_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_until", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["change_id"], ["change_records.id"]),
    )
    for field in ("change_id", "status", "available_at", "claimed_until"):
        op.create_index(f"ix_change_outbox_{field}", "change_outbox", [field])
    op.create_table(
        "git_event_inbox",
        sa.Column("delivery_id", sa.String(128), primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("repository_ref", sa.String(240), nullable=False),
        sa.Column("change_id", sa.String(36)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["change_id"], ["change_records.id"]),
    )
    for field in ("event_type", "repository_ref", "change_id"):
        op.create_index(f"ix_git_event_inbox_{field}", "git_event_inbox", [field])


def downgrade() -> None:
    op.drop_table("git_event_inbox")
    op.drop_table("change_outbox")
    op.drop_table("change_records")
    if op.get_bind().dialect.name != "postgresql":
        sa.Enum(name="changeoutboxstatus").drop(op.get_bind(), checkfirst=True)
        sa.Enum(name="changestatus").drop(op.get_bind(), checkfirst=True)
        sa.Enum(name="changetype").drop(op.get_bind(), checkfirst=True)
