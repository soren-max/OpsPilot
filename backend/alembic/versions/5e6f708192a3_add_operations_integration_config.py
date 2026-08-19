"""add operations integration configuration center

Revision ID: 5e6f708192a3
Revises: 4d5e6f708192
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5e6f708192a3"
down_revision: str | None = "4d5e6f708192"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("hosts") as batch_op:
        batch_op.add_column(sa.Column("address", sa.String(length=253), nullable=True))
        batch_op.add_column(sa.Column("ssh_port", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("ssh_username", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("credential_reference", sa.String(length=80), nullable=True)
        )
    op.create_table(
        "operations_integration_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("environment_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "VALIDATED", "READY", "DISABLED", name="integrationconfigstatus"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("remote_services_path", sa.String(length=512), nullable=False),
        sa.Column("remote_working_directory", sa.String(length=512), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("status_argv", sa.JSON(), nullable=False),
        sa.Column("parser_config", sa.JSON(), nullable=False),
        sa.Column("allowlist", sa.JSON(), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("last_ssh_test_ok", sa.Boolean(), nullable=False),
        sa.Column("last_status_test_ok", sa.Boolean(), nullable=False),
        sa.Column("last_test_details", sa.JSON(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("environment_id"),
    )
    op.create_index(
        "ix_operations_integration_configs_environment_id",
        "operations_integration_configs",
        ["environment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operations_integration_configs_environment_id",
        table_name="operations_integration_configs",
    )
    op.drop_table("operations_integration_configs")
    with op.batch_alter_table("hosts") as batch_op:
        batch_op.drop_column("credential_reference")
        batch_op.drop_column("ssh_username")
        batch_op.drop_column("ssh_port")
        batch_op.drop_column("address")
