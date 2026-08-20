import asyncio
from datetime import UTC, datetime, timedelta

from app.adapters.health import ActionServiceHealthCapability
from app.adapters.mock import MockActionExecutor
from app.adapters.tickets import MockTicketAdapter
from app.application import ActionService
from app.capabilities.health import HealthQuery, HealthStatus
from app.capabilities.tickets import TicketQuery, TicketRecord
from app.domain.actions.policy import ActionPolicyEngine

NOW = datetime(2026, 8, 20, tzinfo=UTC)


def test_mock_ticket_adapter_filters_and_orders_fixture_records() -> None:
    records = tuple(
        TicketRecord(
            id=f"INC-{index}",
            title=f"Payment outage {index}",
            status="resolved",
            service="payment-service",
            environment="test",
            summary="Previous 5xx incident",
            resolution="Restarted service",
            created_at=NOW - timedelta(minutes=index),
            resolved_at=NOW - timedelta(seconds=index),
            source_reference=f"ticket:INC-{index}",
        )
        for index in range(1, 4)
    )
    result = asyncio.run(
        MockTicketAdapter(records).search(
            TicketQuery(
                service="payment-service",
                environment="test",
                status="resolved",
                keywords=("5xx",),
                start=NOW - timedelta(hours=1),
                end=NOW,
                limit=2,
            )
        )
    )
    assert [item.id for item in result] == ["INC-1", "INC-2"]


def test_health_capability_hides_action_execution_semantics() -> None:
    service = ActionService(
        ActionPolicyEngine(frozenset({"web-01"})), MockActionExecutor()
    )
    capability = ActionServiceHealthCapability(service, {"payment-service": "web-01"})
    result = asyncio.run(
        capability.get_service_health(
            HealthQuery(service="payment-service", environment="test")
        )
    )
    assert result.status is HealthStatus.HEALTHY
    assert result.source_reference == "health:target:web-01"
