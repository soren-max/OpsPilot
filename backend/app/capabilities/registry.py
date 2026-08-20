import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypeVar, cast

from app.capabilities.errors import CapabilityError, CapabilityTimeout, CapabilityUnavailable
from app.capabilities.evidence import (
    NormalizedEvidence,
    health_evidence,
    log_evidence,
    metric_evidence,
    ticket_evidence,
)
from app.capabilities.health import HealthCapability, HealthObservation, HealthQuery
from app.capabilities.logs import LogObservation, LogQuery, LogsCapability, LogSeverity
from app.capabilities.metrics import (
    MetricAggregation,
    MetricKind,
    MetricObservation,
    MetricQuery,
    MetricsCapability,
)
from app.capabilities.policy import CapabilityQueryPolicy
from app.capabilities.tickets import TicketQuery, TicketRecord, TicketsCapability

T = TypeVar("T")


@dataclass(frozen=True)
class CapabilityFailure:
    capability: str
    code: str


@dataclass(frozen=True)
class CapabilityCollection:
    evidence: tuple[NormalizedEvidence, ...]
    failures: tuple[CapabilityFailure, ...]


@dataclass(frozen=True)
class IncidentCapabilities:
    policy: CapabilityQueryPolicy
    metrics: MetricsCapability | None = None
    logs: LogsCapability | None = None
    tickets: TicketsCapability | None = None
    health: HealthCapability | None = None
    timeout_seconds: float = 5.0
    lookback: timedelta = timedelta(minutes=15)

    async def collect(
        self, service: str, environment: str, *, now: datetime
    ) -> CapabilityCollection:
        self.policy.validate_service(service)
        end = now
        start = end - self.lookback
        calls: list[tuple[str, Awaitable[object]]] = []
        if self.metrics is not None:
            metric_query = MetricQuery(
                metric_kind=MetricKind.SERVICE_UP,
                service=service,
                environment=environment,
                start=start,
                end=end,
                step_seconds=max(60, self.policy.minimum_step_seconds),
                aggregation=MetricAggregation.AVG,
            )
            self.policy.validate_metric(metric_query)
            calls.append(("metrics", self.metrics.query(metric_query)))
        if self.logs is not None:
            log_query = LogQuery(
                service=service,
                environment=environment,
                start=start,
                end=end,
                severity=LogSeverity.ERROR,
                limit=min(20, self.policy.max_log_entries),
            )
            self.policy.validate_log(log_query)
            calls.append(("logs", self.logs.query(log_query)))
        if self.tickets is not None:
            ticket_query = TicketQuery(
                service=service,
                environment=environment,
                start=start,
                end=end,
                limit=min(10, self.policy.max_ticket_records),
            )
            self.policy.validate_ticket(ticket_query)
            calls.append(("tickets", self.tickets.search(ticket_query)))
        if self.health is not None:
            calls.append(
                (
                    "health",
                    self.health.get_service_health(
                        HealthQuery(service=service, environment=environment)
                    ),
                )
            )
        results = await asyncio.gather(
            *(self._bounded(name, call) for name, call in calls), return_exceptions=True
        )
        evidence: list[NormalizedEvidence] = []
        failures: list[CapabilityFailure] = []
        for (name, _), result in zip(calls, results, strict=True):
            if isinstance(result, BaseException):
                code = (
                    result.code
                    if isinstance(result, CapabilityError)
                    else "CAPABILITY_UNAVAILABLE"
                )
                failures.append(CapabilityFailure(name, code))
                continue
            try:
                if name == "metrics":
                    metric_result = cast(MetricObservation, result)
                    self.policy.validate_series_count(len(metric_result.series))
                    evidence.append(metric_evidence(metric_result))
                elif name == "logs":
                    evidence.append(log_evidence(cast(LogObservation, result)))
                elif name == "tickets":
                    tickets = cast(tuple[TicketRecord, ...], result)
                    evidence.extend(ticket_evidence(item) for item in tickets)
                else:
                    evidence.append(health_evidence(cast(HealthObservation, result)))
            except CapabilityError as exc:
                failures.append(CapabilityFailure(name, exc.code))
        return CapabilityCollection(tuple(evidence), tuple(failures))

    async def _bounded(self, name: str, call: Awaitable[T]) -> T:
        try:
            return await asyncio.wait_for(call, timeout=self.timeout_seconds)
        except TimeoutError as exc:
            raise CapabilityTimeout(f"{name} capability timed out") from exc
        except CapabilityError:
            raise
        except Exception as exc:
            raise CapabilityUnavailable(f"{name} capability is unavailable") from exc
