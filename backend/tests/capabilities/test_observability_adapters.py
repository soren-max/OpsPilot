import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.adapters.http import HttpxJsonClient
from app.adapters.loki import LokiLogsAdapter, render_logql
from app.adapters.prometheus import PrometheusMetricsAdapter, render_promql
from app.capabilities.errors import CapabilityMalformedResponse, CapabilityTimeout
from app.capabilities.logs import LogQuery, LogSeverity
from app.capabilities.metrics import MetricAggregation, MetricKind, MetricQuery

NOW = datetime(2026, 8, 20, tzinfo=UTC)


class StubClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, Mapping[str, str | int | float], Mapping[str, str] | None]] = []

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | float],
        headers: Mapping[str, str] | None = None,
    ) -> object:
        self.calls.append((path, params, headers))
        return self.payload


def metric_query(kind: MetricKind) -> MetricQuery:
    return MetricQuery(
        metric_kind=kind,
        service="payment-service",
        environment="test",
        start=NOW - timedelta(minutes=5),
        end=NOW,
        step_seconds=60,
        aggregation=MetricAggregation.AVG,
    )


@pytest.mark.parametrize("kind", list(MetricKind))
def test_metric_kind_maps_to_controlled_promql(kind: MetricKind) -> None:
    expression = render_promql(metric_query(kind))
    assert 'service="payment-service"' in expression
    assert 'environment="test"' in expression
    assert "raw_promql" not in MetricQuery.model_fields


def test_error_rate_promql_is_a_controlled_ratio() -> None:
    expression = render_promql(metric_query(MetricKind.ERROR_RATE))
    assert 'status=~"5.."' in expression
    assert expression.count('service="payment-service"') == 2


def test_prometheus_range_and_instant_endpoints_are_supported() -> None:
    range_payload = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [{"metric": {"instance": "a"}, "values": [[NOW.timestamp(), "0"]]}],
        },
    }
    range_client = StubClient(range_payload)
    observation = asyncio.run(
        PrometheusMetricsAdapter(range_client).query(metric_query(MetricKind.SERVICE_UP))
    )
    assert range_client.calls[0][0] == "/api/v1/query_range"
    assert observation.series[0].points[0].value == 0
    assert observation.source_reference.startswith("prometheus:query:")

    instant_payload = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [{"metric": {}, "value": [NOW.timestamp(), "1"]}],
        },
    }
    instant_client = StubClient(instant_payload)
    asyncio.run(
        PrometheusMetricsAdapter(instant_client).instant(
            metric_query(MetricKind.SERVICE_UP), at=NOW
        )
    )
    assert instant_client.calls[0][0] == "/api/v1/query"


def test_malformed_prometheus_response_fails_closed() -> None:
    with pytest.raises(CapabilityMalformedResponse, match="Prometheus"):
        asyncio.run(
            PrometheusMetricsAdapter(StubClient({"status": "success", "data": {}})).query(
                metric_query(MetricKind.SERVICE_UP)
            )
        )


def log_query(*, limit: int = 10) -> LogQuery:
    return LogQuery(
        service="payment-service",
        environment="test",
        start=NOW - timedelta(minutes=5),
        end=NOW,
        severity=LogSeverity.ERROR,
        keywords=("connection refused",),
        limit=limit,
    )


def test_log_query_maps_to_controlled_logql_and_bounded_parameters() -> None:
    expression = render_logql(log_query())
    assert expression == (
        '{service="payment-service",environment="test"} '
        '| level="error" |= "connection refused"'
    )
    assert "raw_logql" not in LogQuery.model_fields


def test_loki_response_is_truncated_to_caller_limit() -> None:
    payload = {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {"level": "error", "secret": "redacted-by-selection"},
                    "values": [
                        [str(int(NOW.timestamp() * 1_000_000_000) - index), f"error {index}"]
                        for index in range(5)
                    ],
                }
            ],
        },
    }
    client = StubClient(payload)
    result = asyncio.run(LokiLogsAdapter(client, tenant="tenant-a").query(log_query(limit=2)))
    assert len(result.entries) == 2
    assert client.calls[0][0] == "/loki/api/v1/query_range"
    assert client.calls[0][1]["limit"] == 2
    assert client.calls[0][2] == {"X-Scope-OrgID": "tenant-a"}
    assert result.source_reference.startswith("loki:query:")
    assert "secret" not in result.entries[0].labels


def test_malformed_loki_response_fails_closed() -> None:
    with pytest.raises(CapabilityMalformedResponse, match="Loki"):
        asyncio.run(LokiLogsAdapter(StubClient({"status": "success"})).query(log_query()))


def test_http_timeout_and_secret_do_not_leak() -> None:
    token = "test-sensitive-token"

    async def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("transport included no credentials")

    client = HttpxJsonClient(
        "https://prometheus.example.test",
        timeout_seconds=0.1,
        default_headers={"Authorization": f"Bearer {token}"},
        transport=httpx.MockTransport(timeout),
    )
    with pytest.raises(CapabilityTimeout) as captured:
        asyncio.run(client.get_json("/api/v1/query", params={"query": "up"}))
    assert token not in str(captured.value)


def test_http_response_size_limit_fails_closed() -> None:
    def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 101)

    client = HttpxJsonClient(
        "https://loki.example.test",
        timeout_seconds=1,
        max_response_bytes=100,
        transport=httpx.MockTransport(oversized),
    )
    with pytest.raises(CapabilityMalformedResponse, match="size limit"):
        asyncio.run(client.get_json("/loki/api/v1/query_range", params={"limit": 1}))
