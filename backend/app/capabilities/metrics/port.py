from typing import Protocol

from app.capabilities.metrics.models import MetricObservation, MetricQuery


class MetricsCapability(Protocol):
    async def query(self, query: MetricQuery) -> MetricObservation: ...
