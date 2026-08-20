from datetime import UTC, datetime

from app.application.action_service import ActionService
from app.capabilities.errors import CapabilityUnavailable
from app.capabilities.health import HealthObservation, HealthQuery, HealthStatus
from app.domain.actions.models import (
    ActionRequest,
    ActionType,
    ServiceActionParams,
    TargetEnvironment,
)


class ActionServiceHealthCapability:
    """Investigation-facing health port backed by the controlled read-only Action boundary."""

    def __init__(self, action_service: ActionService, targets_by_service: dict[str, str]) -> None:
        self._action_service = action_service
        self._targets_by_service = dict(targets_by_service)

    async def get_service_health(self, query: HealthQuery) -> HealthObservation:
        target = self._targets_by_service.get(query.service)
        if target is None:
            raise CapabilityUnavailable("No enabled health target is configured for service")
        environment = {
            "production": TargetEnvironment.PRODUCTION,
            "prod": TargetEnvironment.PRODUCTION,
            "test": TargetEnvironment.TEST,
            "test-mock": TargetEnvironment.TEST,
        }.get(query.environment.lower(), TargetEnvironment.DEVELOPMENT)
        action = ActionRequest(
            action_type=ActionType.GET_SERVICE_STATUS,
            target=target,
            environment=environment,
            parameters=ServiceActionParams(service=query.service),
            reason="Collect bounded service health evidence for incident investigation.",
        )
        outcome = await self._action_service.execute(action)
        if outcome.result is None or outcome.verification is None:
            raise CapabilityUnavailable("Service health query was rejected or unavailable")
        status = HealthStatus.HEALTHY if outcome.verification.verified else HealthStatus.UNAVAILABLE
        now = datetime.now(UTC)
        return HealthObservation(
            service=query.service,
            environment=query.environment,
            status=status,
            summary=(
                f"Service {query.service} is healthy."
                if status is HealthStatus.HEALTHY
                else f"Service {query.service} is unavailable."
            ),
            source_reference=f"health:target:{target}",
            observed_at=outcome.result.finished_at,
            collected_at=now,
        )
