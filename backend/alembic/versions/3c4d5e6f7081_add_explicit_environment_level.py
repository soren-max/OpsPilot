"""add explicit environment level

Revision ID: 3c4d5e6f7081
Revises: 2b3c4d5e6f70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c4d5e6f7081"
down_revision: str | None = "2b3c4d5e6f70"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("environments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "environment_level",
                sa.String(20),
                nullable=False,
                server_default="DEVELOPMENT",
            )
        )
    with op.batch_alter_table("task_logs") as batch_op:
        batch_op.alter_column(
            "stream",
            existing_type=sa.String(10),
            type_=sa.String(32),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("task_logs") as batch_op:
        batch_op.alter_column(
            "stream",
            existing_type=sa.String(32),
            type_=sa.String(10),
            existing_nullable=False,
        )
    with op.batch_alter_table("environments") as batch_op:
        batch_op.drop_column("environment_level")
