"""SQLAlchemy persistence models for the incident bounded context."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime
from app.domain.audit.models import ActorType, AuditEventType
from app.domain.incidents.diagnosis import HypothesisStatus
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import IncidentStatus, Severity
from app.models import uuid_str


class IncidentRecord(TimestampMixin, Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), index=True, nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus), index=True, nullable=False)
    environment: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    service: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evidence: Mapped[list["EvidenceRecord"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    hypotheses: Mapped[list["HypothesisRecord"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    diagnoses: Mapped[list["DiagnosisRecord"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    actions: Mapped[list["IncidentActionLinkRecord"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class EvidenceRecord(Base):
    __tablename__ = "incident_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    evidence_type: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    collector: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    incident: Mapped[IncidentRecord] = relationship(back_populates="evidence")
    __table_args__ = (
        UniqueConstraint("incident_id", "fingerprint", name="uq_evidence_incident_fingerprint"),
    )


class HypothesisRecord(Base):
    __tablename__ = "incident_hypotheses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[HypothesisStatus] = mapped_column(Enum(HypothesisStatus), nullable=False)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    contradicting_evidence_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    incident: Mapped[IncidentRecord] = relationship(back_populates="hypotheses")


class DiagnosisRecord(Base):
    __tablename__ = "incident_diagnoses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    contributing_factors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    incident: Mapped[IncidentRecord] = relationship(back_populates="diagnoses")


class IncidentAuditEventRecord(Base):
    __tablename__ = "incident_audit_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    event_type: Mapped[AuditEventType] = mapped_column(Enum(AuditEventType), index=True)
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    causation_id: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True, nullable=False)
    payload_summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


@event.listens_for(IncidentAuditEventRecord, "before_update")
@event.listens_for(IncidentAuditEventRecord, "before_delete")
def prevent_incident_audit_mutation(
    _mapper: object, _connection: object, _event: IncidentAuditEventRecord
) -> None:
    raise ValueError("Incident AuditEvent is append-only")


class IncidentActionLinkRecord(Base):
    __tablename__ = "incident_action_links"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("operation_tasks.id"), primary_key=True)
    action_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    incident: Mapped[IncidentRecord] = relationship(back_populates="actions")
