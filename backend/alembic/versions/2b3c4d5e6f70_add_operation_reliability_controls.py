"""add operation reliability controls

Revision ID: 2b3c4d5e6f70
Revises: 1a2b3c4d5e6f
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2b3c4d5e6f70"
down_revision: str | None = "1a2b3c4d5e6f"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("operation_tasks") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(128)))
        batch_op.add_column(sa.Column("request_fingerprint", sa.String(64)))
        batch_op.add_column(
            sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column(
                "partial_failure_policy",
                sa.String(20),
                nullable=False,
                server_default="NONE",
            )
        )
        batch_op.create_unique_constraint(
            "uq_operation_tasks_requested_by_idempotency_key",
            ["requested_by", "idempotency_key"],
        )
    with op.batch_alter_table("operation_targets") as batch_op:
        batch_op.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("verification_status", sa.String(30)))
        batch_op.add_column(sa.Column("verification_output", sa.Text()))
    with op.batch_alter_table("operation_requests") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(128)))
        batch_op.add_column(sa.Column("request_fingerprint", sa.String(64)))
        batch_op.create_unique_constraint(
            "uq_operation_requests_requested_by_idempotency_key",
            ["requested_by", "idempotency_key"],
        )
    op.create_table(
        "operation_locks",
        sa.Column(
            "environment_id",
            sa.String(36),
            sa.ForeignKey("environments.id"),
            primary_key=True,
        ),
        sa.Column("service_id", sa.String(36), sa.ForeignKey("services.id"), primary_key=True),
        sa.Column("host_id", sa.String(36), sa.ForeignKey("hosts.id"), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("operation_tasks.id"), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_operation_locks_task_id", "operation_locks", ["task_id"])


def downgrade() -> None:
    op.drop_table("operation_locks")
    with op.batch_alter_table("operation_requests") as batch_op:
        batch_op.drop_constraint(
            "uq_operation_requests_requested_by_idempotency_key", type_="unique"
        )
        batch_op.drop_column("request_fingerprint")
        batch_op.drop_column("idempotency_key")
    with op.batch_alter_table("operation_targets") as batch_op:
        batch_op.drop_column("verification_output")
        batch_op.drop_column("verification_status")
        batch_op.drop_column("attempt_count")
    with op.batch_alter_table("operation_tasks") as batch_op:
        batch_op.drop_constraint(
            "uq_operation_tasks_requested_by_idempotency_key", type_="unique"
        )
        batch_op.drop_column("partial_failure_policy")
        batch_op.drop_column("cancel_requested")
        batch_op.drop_column("request_fingerprint")
        batch_op.drop_column("idempotency_key")
