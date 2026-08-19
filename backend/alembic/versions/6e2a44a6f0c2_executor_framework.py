"""executor framework persistence

Revision ID: 6e2a44a6f0c2
Revises: 3bdc21ee176f
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6e2a44a6f0c2"
down_revision: Union[str, None] = "3bdc21ee176f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("stream", sa.String(length=10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["operation_tasks.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["operation_targets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_logs_task_id", "task_logs", ["task_id"])
    op.create_index("ix_task_logs_target_id", "task_logs", ["target_id"])
    op.create_table(
        "service_status_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("environment_id", sa.String(length=36), nullable=False),
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.Column("host_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "SUCCEEDED", "FAILED", "TIMED_OUT", "UNREACHABLE", "UNKNOWN", name="targetstatus"), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"]),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["operation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("environment_id", "service_id", "host_id"),
    )
    op.create_index("ix_service_status_snapshots_environment_id", "service_status_snapshots", ["environment_id"])
    op.create_index("ix_service_status_snapshots_service_id", "service_status_snapshots", ["service_id"])
    op.create_index("ix_service_status_snapshots_host_id", "service_status_snapshots", ["host_id"])
    op.create_index("ix_service_status_snapshots_task_id", "service_status_snapshots", ["task_id"])
    op.create_table(
        "topology_sync_states",
        sa.Column("environment_id", sa.String(length=36), nullable=False),
        sa.Column("last_task_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.Enum("PENDING", "RUNNING", "SUCCEEDED", "PARTIALLY_SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "REJECTED", name="taskstatus"), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"]),
        sa.ForeignKeyConstraint(["last_task_id"], ["operation_tasks.id"]),
        sa.PrimaryKeyConstraint("environment_id"),
    )


def downgrade() -> None:
    op.drop_table("topology_sync_states")
    op.drop_table("service_status_snapshots")
    op.drop_table("task_logs")
