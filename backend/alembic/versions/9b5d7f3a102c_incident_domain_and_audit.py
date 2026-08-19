"""incident domain and append-only audit

Revision ID: 9b5d7f3a102c
Revises: 8a4c6e2f901b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b5d7f3a102c"
down_revision: str | None = "8a4c6e2f901b"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

severity = sa.Enum("CRITICAL", "HIGH", "MEDIUM", "LOW", name="severity")
incident_status = sa.Enum(
    "OPEN", "INVESTIGATING", "MITIGATING", "VERIFYING", "RESOLVED", "CLOSED", "FAILED",
    name="incidentstatus",
)
evidence_type = sa.Enum(
    "ALERT", "METRIC", "LOG", "TICKET", "SERVICE_STATUS", "OPERATOR_NOTE", "TOOL_RESULT",
    name="evidencetype",
)
hypothesis_status = sa.Enum(
    "PROPOSED", "SUPPORTED", "REJECTED", "CONFIRMED", name="hypothesisstatus"
)
audit_event_type = sa.Enum(
    "INCIDENT_CREATED", "INCIDENT_STATE_CHANGED", "EVIDENCE_ADDED", "HYPOTHESIS_ADDED",
    "HYPOTHESIS_UPDATED", "DIAGNOSIS_RECORDED", "ACTION_PROPOSED", "RISK_ASSESSED",
    "APPROVAL_REQUESTED", "APPROVAL_GRANTED", "APPROVAL_REJECTED", "ACTION_EXECUTED",
    "ACTION_FAILED", "VERIFICATION_RECORDED", "INCIDENT_RESOLVED", "INCIDENT_CLOSED",
    name="auditeventtype",
)
actor_type = sa.Enum("HUMAN", "SYSTEM", "AGENT", "TOOL", name="actortype")


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("status", incident_status, nullable=False),
        sa.Column("environment", sa.String(80), nullable=False),
        sa.Column("service", sa.String(120), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("severity", "status", "environment", "service"):
        op.create_index(f"ix_incidents_{column}", "incidents", [column])
    op.create_table(
        "incident_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("evidence_type", evidence_type, nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("source_reference", sa.String(1000), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("excerpt", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collector", sa.String(120), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "incident_id", "fingerprint", name="uq_evidence_incident_fingerprint"
        ),
    )
    op.create_index("ix_incident_evidence_incident_id", "incident_evidence", ["incident_id"])
    op.create_table(
        "incident_hypotheses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", hypothesis_status, nullable=False),
        sa.Column("supporting_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("contradicting_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(80), nullable=False),
    )
    op.create_index(
        "ix_incident_hypotheses_incident_id", "incident_hypotheses", ["incident_id"]
    )
    op.create_table(
        "incident_diagnoses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("contributing_factors", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_incident_diagnoses_incident_id", "incident_diagnoses", ["incident_id"]
    )
    op.create_table(
        "incident_audit_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("event_type", audit_event_type, nullable=False),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("actor_id", sa.String(80), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("causation_id", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_summary", sa.String(1000), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    for column in ("incident_id", "event_type", "correlation_id", "occurred_at"):
        op.create_index(
            f"ix_incident_audit_events_{column}", "incident_audit_events", [column]
        )
    op.create_table(
        "incident_action_links",
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), primary_key=True),
        sa.Column(
            "task_id", sa.String(36), sa.ForeignKey("operation_tasks.id"), primary_key=True
        ),
        sa.Column("action_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("incident_action_links")
    for column in ("occurred_at", "correlation_id", "event_type", "incident_id"):
        op.drop_index(f"ix_incident_audit_events_{column}", table_name="incident_audit_events")
    op.drop_table("incident_audit_events")
    op.drop_index("ix_incident_diagnoses_incident_id", table_name="incident_diagnoses")
    op.drop_table("incident_diagnoses")
    op.drop_index("ix_incident_hypotheses_incident_id", table_name="incident_hypotheses")
    op.drop_table("incident_hypotheses")
    op.drop_index("ix_incident_evidence_incident_id", table_name="incident_evidence")
    op.drop_table("incident_evidence")
    for column in ("service", "environment", "status", "severity"):
        op.drop_index(f"ix_incidents_{column}", table_name="incidents")
    op.drop_table("incidents")
    bind = op.get_bind()
    for enum in (
        actor_type, audit_event_type, hypothesis_status, evidence_type, incident_status, severity
    ):
        enum.drop(bind, checkfirst=True)
