"""workflow run metadata and evaluation hooks

Revision ID: a6c8e0f2143d
Revises: 9b5d7f3a102c
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6c8e0f2143d"
down_revision: str | None = "9b5d7f3a102c"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

workflow_status = sa.Enum(
    "PENDING", "RUNNING", "WAITING", "SUCCEEDED", "FAILED", "CANCELLED",
    name="workflowrunstatus",
)


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("graph_name", sa.String(80), nullable=False),
        sa.Column("graph_version", sa.String(32), nullable=False),
        sa.Column("status", workflow_status, nullable=False),
        sa.Column("started_by", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("current_node", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_checkpoint_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("hypothesis_id", sa.String(36)),
        sa.Column("diagnosis_id", sa.String(36)),
        sa.Column("proposed_action_id", sa.String(64)),
        sa.Column("execution_task_id", sa.String(64)),
        sa.Column("state_references", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "incident_id", "started_by", "idempotency_key",
            name="uq_workflow_run_incident_actor_idempotency",
        ),
    )
    op.create_index("ix_workflow_runs_incident_id", "workflow_runs", ["incident_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_table(
        "workflow_evaluation_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("expected_outcome", sa.String(500), nullable=False),
        sa.Column("actual_outcome", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_evaluation_records_incident_id", "workflow_evaluation_records", ["incident_id"]
    )
    op.create_index(
        "ix_workflow_evaluation_records_workflow_id", "workflow_evaluation_records", ["workflow_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_evaluation_records_workflow_id", table_name="workflow_evaluation_records"
    )
    op.drop_index(
        "ix_workflow_evaluation_records_incident_id", table_name="workflow_evaluation_records"
    )
    op.drop_table("workflow_evaluation_records")
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_incident_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    workflow_status.drop(op.get_bind(), checkfirst=True)
