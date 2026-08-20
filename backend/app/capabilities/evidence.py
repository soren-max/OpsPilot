from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.capabilities.health.models import HealthObservation
from app.capabilities.logs.models import LogObservation
from app.capabilities.metrics.models import MetricObservation
from app.capabilities.tickets.models import TicketRecord
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import JsonValue


class NormalizedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_type: EvidenceType
    source: str = Field(min_length=1, max_length=120)
    source_reference: str = Field(min_length=1, max_length=1000)
    summary: str = Field(min_length=1, max_length=1000)
    excerpt: str | None = Field(default=None, max_length=8000)
    observed_at: datetime
    collector: str = Field(min_length=1, max_length=120)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


def metric_evidence(item: MetricObservation) -> NormalizedEvidence:
    selected_values: list[JsonValue] = []
    for series in item.series:
        selected_values.extend(point.value for point in series.points)
    selected_values = selected_values[-10:]
    return NormalizedEvidence(
        evidence_type=EvidenceType.METRIC,
        source="prometheus",
        source_reference=item.source_reference,
        summary=item.summary,
        observed_at=item.end,
        collector="metrics-capability",
        metadata={
            "metric_kind": item.query_kind.value,
            "service": item.service,
            "environment": item.environment,
            "series_count": len(item.series),
            "selected_values": selected_values,
        },
    )


def log_evidence(item: LogObservation) -> NormalizedEvidence:
    excerpt = "\n".join(entry.message_excerpt for entry in item.entries)[:8000] or None
    return NormalizedEvidence(
        evidence_type=EvidenceType.LOG,
        source="loki",
        source_reference=item.source_reference,
        summary=item.summary,
        excerpt=excerpt,
        observed_at=max((entry.timestamp for entry in item.entries), default=item.end),
        collector="logs-capability",
        metadata={
            "service": item.service,
            "environment": item.environment,
            "entry_count": len(item.entries),
        },
    )


def ticket_evidence(item: TicketRecord) -> NormalizedEvidence:
    return NormalizedEvidence(
        evidence_type=EvidenceType.TICKET,
        source="mock-ticket",
        source_reference=item.source_reference,
        summary=f"{item.id}: {item.title} ({item.status})",
        excerpt=item.resolution or item.summary,
        observed_at=item.resolved_at or item.created_at,
        collector="ticket-capability",
        metadata={
            "ticket_id": item.id,
            "service": item.service,
            "environment": item.environment,
            "status": item.status,
        },
    )


def health_evidence(item: HealthObservation) -> NormalizedEvidence:
    return NormalizedEvidence(
        evidence_type=EvidenceType.SERVICE_STATUS,
        source="service-health",
        source_reference=item.source_reference,
        summary=item.summary,
        observed_at=item.observed_at,
        collector="health-capability",
        metadata={
            "service": item.service,
            "environment": item.environment,
            "status": item.status.value,
        },
    )
