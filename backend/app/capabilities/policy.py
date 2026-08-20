from dataclasses import dataclass
from datetime import datetime, timedelta

from app.capabilities.errors import CapabilityQueryRejected
from app.capabilities.logs.models import LogQuery
from app.capabilities.metrics.models import MetricKind, MetricQuery
from app.capabilities.tickets.models import TicketQuery


@dataclass(frozen=True)
class CapabilityQueryPolicy:
    allowed_services: frozenset[str]
    max_time_range: timedelta = timedelta(hours=1)
    max_log_entries: int = 100
    max_metric_series: int = 20
    minimum_step_seconds: int = 15
    allowed_metric_kinds: frozenset[MetricKind] = frozenset(MetricKind)
    allowed_log_labels: frozenset[str] = frozenset({"service", "environment", "level"})
    allowed_ticket_filters: frozenset[str] = frozenset(
        {"service", "environment", "status", "keywords", "time_range", "limit"}
    )
    max_ticket_records: int = 20

    def validate_metric(self, query: MetricQuery) -> None:
        self._validate_common(query.service, query.start, query.end)
        if query.metric_kind not in self.allowed_metric_kinds:
            raise CapabilityQueryRejected("Metric kind is not permitted")
        if query.step_seconds < self.minimum_step_seconds:
            raise CapabilityQueryRejected("Metric step is below the configured minimum")

    def validate_log(self, query: LogQuery) -> None:
        self._validate_common(query.service, query.start, query.end)
        if query.limit > self.max_log_entries:
            raise CapabilityQueryRejected("Log result limit exceeds policy")
        if any(not keyword.strip() or len(keyword) > 80 for keyword in query.keywords):
            raise CapabilityQueryRejected("Log keywords must be non-empty and bounded")

    def validate_ticket(self, query: TicketQuery) -> None:
        self._validate_common(query.service, query.start, query.end)
        if query.limit > self.max_ticket_records:
            raise CapabilityQueryRejected("Ticket result limit exceeds policy")
        if any(not keyword.strip() or len(keyword) > 80 for keyword in query.keywords):
            raise CapabilityQueryRejected("Ticket keywords must be non-empty and bounded")

    def validate_series_count(self, count: int) -> None:
        if count > self.max_metric_series:
            raise CapabilityQueryRejected("Metric series count exceeds policy")

    def validate_service(self, service: str) -> None:
        if service not in self.allowed_services:
            raise CapabilityQueryRejected("Service is outside the configured allowlist")

    def _validate_common(self, service: str, start: datetime, end: datetime) -> None:
        self.validate_service(service)
        if start.utcoffset() is None or end.utcoffset() is None:
            raise CapabilityQueryRejected("Query timestamps must include a timezone")
        if end <= start:
            raise CapabilityQueryRejected("Query end must be after start")
        if end - start > self.max_time_range:
            raise CapabilityQueryRejected("Query time range exceeds policy")
