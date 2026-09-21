"""add execution-safety and redaction audit event values

Revision ID: f1b3d5c7e9a1
Revises: e0a2b4c6d8f0
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1b3d5c7e9a1"
down_revision: str | None = "e0a2b4c6d8f0"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

AUDIT_EVENTS = (
    "EXECUTION_BLOCKED",
    "APPROVAL_STALE",
    "SENSITIVE_DATA_REDACTED",
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for value in AUDIT_EVENTS:
            op.execute(f"ALTER TYPE auditeventtype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove enum values in place. The application no longer emits
    # these values after downgrade; preserving historical audit rows is intentional.
    pass