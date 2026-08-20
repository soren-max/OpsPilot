"""add LLM investigation audit event values

Revision ID: b7d9f1a3052e
Revises: a6c8e0f2143d
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b7d9f1a3052e"
down_revision: str | None = "a6c8e0f2143d"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

AUDIT_EVENTS = (
    "WORKFLOW_STARTED",
    "WORKFLOW_NODE_STARTED",
    "WORKFLOW_NODE_COMPLETED",
    "WORKFLOW_PAUSED",
    "WORKFLOW_FAILED",
    "WORKFLOW_COMPLETED",
    "LLM_INVESTIGATION_STARTED",
    "LLM_INVESTIGATION_COMPLETED",
    "LLM_INVESTIGATION_FAILED",
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for value in AUDIT_EVENTS:
            op.execute(f"ALTER TYPE auditeventtype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove enum values in place. The application no longer emits
    # these values after downgrade; preserving historical audit rows is intentional.
    pass
