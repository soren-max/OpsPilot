from datetime import UTC, datetime, timedelta

import pytest

from app.capabilities.errors import CapabilityQueryRejected
from app.capabilities.logs import LogQuery
from app.capabilities.metrics import MetricKind, MetricQuery
from app.capabilities.policy import CapabilityQueryPolicy
from app.capabilities.tickets import TicketQuery

NOW = datetime(2026, 8, 20, tzinfo=UTC)


def policy() -> CapabilityQueryPolicy:
    return CapabilityQueryPolicy(
        allowed_services=frozenset({"payment-service"}),
        max_time_range=timedelta(hours=1),
        max_log_entries=50,
        max_metric_series=2,
        minimum_step_seconds=15,
        max_ticket_records=10,
    )


@pytest.mark.parametrize(
    ("kind", "query"),
    [
        (
            "metric",
            MetricQuery(
                metric_kind=MetricKind.SERVICE_UP,
                service="payment-service",
                environment="test",
                start=NOW - timedelta(days=365 * 5),
                end=NOW,
                step_seconds=60,
            ),
        ),
        (
            "metric",
            MetricQuery(
                metric_kind=MetricKind.SERVICE_UP,
                service="payment-service",
                environment="test",
                start=NOW - timedelta(minutes=5),
                end=NOW,
                step_seconds=1,
            ),
        ),
        (
            "log",
            LogQuery(
                service="payment-service",
                environment="test",
                start=NOW - timedelta(minutes=5),
                end=NOW,
                limit=1000,
            ),
        ),
        (
            "ticket",
            TicketQuery(
                service="payment-service",
                environment="test",
                start=NOW - timedelta(minutes=5),
                end=NOW,
                limit=20,
            ),
        ),
    ],
)
def test_query_limits_fail_closed(kind: str, query: object) -> None:
    with pytest.raises(CapabilityQueryRejected):
        if kind == "metric":
            policy().validate_metric(query)  # type: ignore[arg-type]
        elif kind == "log":
            policy().validate_log(query)  # type: ignore[arg-type]
        else:
            policy().validate_ticket(query)  # type: ignore[arg-type]


def test_unknown_service_is_rejected() -> None:
    query = MetricQuery(
        metric_kind=MetricKind.ERROR_RATE,
        service="unknown-service",
        environment="test",
        start=NOW - timedelta(minutes=5),
        end=NOW,
        step_seconds=60,
    )
    with pytest.raises(CapabilityQueryRejected, match="allowlist"):
        policy().validate_metric(query)


def test_metric_series_limit_is_enforced() -> None:
    with pytest.raises(CapabilityQueryRejected, match="series"):
        policy().validate_series_count(3)
