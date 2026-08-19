"""add password and account status to users

Revision ID: c9d7e1a3b5f4
Revises: 8f1e7b1a4c3d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d7e1a3b5f4"
down_revision: str | None = "8f1e7b1a4c3d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Nullable password_hash lets historic accounts be preserved without
    # inventing or resetting credentials. New/bootstrap users always receive a hash.
    existing_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    with op.batch_alter_table("users") as batch_op:
        if "password_hash" not in existing_columns:
            batch_op.add_column(sa.Column("password_hash", sa.String(length=256), nullable=True))
        if "status" not in existing_columns:
            batch_op.add_column(
                sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE")
            )


def downgrade() -> None:
    existing_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    with op.batch_alter_table("users") as batch_op:
        if "status" in existing_columns:
            batch_op.drop_column("status")
        if "password_hash" in existing_columns:
            batch_op.drop_column("password_hash")
