"""link approved operation requests to tasks

Revision ID: 1a2b3c4d5e6f
Revises: c9d7e1a3b5f4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1a2b3c4d5e6f"
down_revision: str | None = "c9d7e1a3b5f4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("operation_requests") as batch_op:
        batch_op.drop_constraint(
            "fk_operation_requests_task_id_operation_tasks", type_="foreignkey"
        )
    with op.batch_alter_table("operation_tasks") as batch_op:
        batch_op.add_column(sa.Column("operation_request_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_operation_tasks_operation_request_id_operation_requests",
            "operation_requests",
            ["operation_request_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_operation_tasks_operation_request_id", ["operation_request_id"]
        )
    with op.batch_alter_table("approval_records") as batch_op:
        batch_op.create_unique_constraint(
            "uq_approval_records_operation_request_id_approver_id",
            ["operation_request_id", "approver_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("approval_records") as batch_op:
        batch_op.drop_constraint(
            "uq_approval_records_operation_request_id_approver_id", type_="unique"
        )
    with op.batch_alter_table("operation_tasks") as batch_op:
        batch_op.drop_constraint(
            "fk_operation_tasks_operation_request_id_operation_requests", type_="foreignkey"
        )
        # MySQL requires the supporting index until the foreign key is gone.
        batch_op.drop_index("ix_operation_tasks_operation_request_id")
        batch_op.drop_column("operation_request_id")
    with op.batch_alter_table("operation_requests") as batch_op:
        batch_op.create_foreign_key(
            "fk_operation_requests_task_id_operation_tasks",
            "operation_tasks",
            ["task_id"],
            ["id"],
        )
