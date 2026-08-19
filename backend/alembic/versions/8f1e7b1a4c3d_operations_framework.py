"""operations RBAC and approval framework

Revision ID: 8f1e7b1a4c3d
Revises: 6e2a44a6f0c2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f1e7b1a4c3d"
down_revision: str | None = "6e2a44a6f0c2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("username", sa.String(80), nullable=False, unique=True), sa.Column("display_name", sa.String(120), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("roles", sa.Column("id", sa.String(36), primary_key=True), sa.Column("code", sa.String(80), nullable=False, unique=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("permissions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("code", sa.String(120), nullable=False, unique=True), sa.Column("description", sa.String(255)))
    op.create_table("user_roles", sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True), sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), primary_key=True))
    op.create_table("role_permissions", sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), primary_key=True), sa.Column("permission_id", sa.String(36), sa.ForeignKey("permissions.id"), primary_key=True))
    op.create_table("operation_requests", sa.Column("id", sa.String(36), primary_key=True), sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("action", sa.String(80), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("task_id", sa.String(36), sa.ForeignKey("operation_tasks.id")), sa.Column("reason", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_operation_requests_requested_by", "operation_requests", ["requested_by"])
    op.create_table("approval_records", sa.Column("id", sa.String(36), primary_key=True), sa.Column("operation_request_id", sa.String(36), sa.ForeignKey("operation_requests.id"), nullable=False), sa.Column("approver_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("decision", sa.String(20), nullable=False), sa.Column("comment", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_approval_records_operation_request_id", "approval_records", ["operation_request_id"])
    op.create_index("ix_approval_records_approver_id", "approval_records", ["approver_id"])


def downgrade() -> None:
    op.drop_table("approval_records")
    op.drop_table("operation_requests")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
