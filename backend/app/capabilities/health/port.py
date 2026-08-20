from typing import Protocol

from app.capabilities.health.models import HealthObservation, HealthQuery


class HealthCapability(Protocol):
    async def get_service_health(self, query: HealthQuery) -> HealthObservation: ...
