"""add dynamic write command argv

Revision ID: 7f3b55c910d4
Revises: 5e6f708192a3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7f3b55c910d4"
down_revision: str | None = "5e6f708192a3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("operations_integration_configs") as batch_op:
        # MySQL rejects string defaults on JSON columns. Add nullable columns,
        # backfill existing rows through SQLAlchemy's JSON binder, then enforce
        # NOT NULL without retaining a database default. Application defaults
        # remain owned by the ORM and configuration API.
        batch_op.add_column(sa.Column("start_argv", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("stop_argv", sa.JSON(), nullable=True))
    table = sa.table(
        "operations_integration_configs",
        sa.column("start_argv", sa.JSON()),
        sa.column("stop_argv", sa.JSON()),
    )
    op.execute(table.update().values(start_argv=[], stop_argv=[]))
    with op.batch_alter_table("operations_integration_configs") as batch_op:
        batch_op.alter_column("start_argv", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("stop_argv", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("operations_integration_configs") as batch_op:
        batch_op.drop_column("stop_argv")
        batch_op.drop_column("start_argv")
