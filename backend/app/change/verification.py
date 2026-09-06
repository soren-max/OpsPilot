"""Current-state verification through the existing read-only capability ports."""

import asyncio
import hashlib
import math
from datetime import timedelta

from sqlalchemy.orm import Session

from app.capabilities import IncidentCapabilities
from app.capabilities.evidence import health_evidence, log_evidence, metric_evidence
from app.capabilities.health import HealthQuery, HealthStatus
from app.capabilities.logs import LogQuery, LogSeverity
from app.capabilities.metrics import MetricKind, MetricQuery
from app.db.base import utc_now
from app.repositories.incident_models import EvidenceRecord, IncidentRecord


class CapabilityChangeVerifier:
    def __init__(
        self,
        db: Session,
        capabilities: IncidentCapabilities,
        *,
        profiles: frozenset[str],
        max_error_rate: float = 0.01,
    ) -> None:
        self.db = db
        self.capabilities = capabilities
        self.profiles = profiles
        self.max_error_rate = max_error_rate

    async def verify(self, incident_id: str, verification_profile_ref: str) -> bool:
        c = self.capabilities
        incident = self.db.get(IncidentRecord, incident_id)
        if (
            incident is None
            or verification_profile_ref not in self.profiles
            or c.health is None
            or c.metrics is None
            or c.logs is None
        ):
            return False
        now = utc_now()
        start = now - timedelta(seconds=60)
        service, environment = incident.service, incident.environment
        metric_query = MetricQuery(
            metric_kind=MetricKind.ERROR_RATE,
            service=service,
            environment=environment,
            start=start,
            end=now,
            step_seconds=60,
        )
        log_query = LogQuery(
            service=service,
            environment=environment,
            start=start,
            end=now,
            severity=LogSeverity.ERROR,
            limit=20,
        )
        c.policy.validate_service(service)
        c.policy.validate_metric(metric_query)
        c.policy.validate_log(log_query)
        health, metrics, logs = await asyncio.wait_for(
            asyncio.gather(
                c.health.get_service_health(HealthQuery(service=service, environment=environment)),
                c.metrics.query(metric_query),
                c.logs.query(log_query),
            ),
            timeout=c.timeout_seconds,
        )
        observations = (health, metrics, logs)
        if any((item.service, item.environment) != (service, environment) for item in observations):
            return False
        if any(not start <= item.collected_at <= utc_now() for item in observations):
            return False
        points = [point for series in metrics.series for point in series.points]
        passed = (
            health.status is HealthStatus.HEALTHY
            and start <= health.observed_at <= now
            and metrics.query_kind is MetricKind.ERROR_RATE
            and bool(points)
            and all(
                start <= p.timestamp <= now
                and math.isfinite(p.value)
                and 0 <= p.value <= self.max_error_rate
                for p in points
            )
            and not logs.entries
        )
        for item in (health_evidence(health), metric_evidence(metrics), log_evidence(logs)):
            self.db.add(
                EvidenceRecord(
                    incident_id=incident.id,
                    evidence_type=item.evidence_type,
                    source=item.source,
                    source_reference=item.source_reference,
                    summary=item.summary,
                    observed_at=item.observed_at,
                    collected_at=utc_now(),
                    collector="change-verifier",
                    evidence_metadata={
                        **item.metadata,
                        "verification_profile": verification_profile_ref,
                    },
                    fingerprint=hashlib.sha256(item.model_dump_json().encode()).hexdigest(),
                )
            )
        self.db.flush()
        return passed
