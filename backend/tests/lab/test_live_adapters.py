import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.http import HttpxJsonClient
from app.adapters.loki import LokiLogsAdapter
from app.adapters.prometheus import PrometheusMetricsAdapter
from app.capabilities.logs import LogQuery
from app.capabilities.metrics import MetricKind, MetricQuery


@pytest.mark.skipif("OPSPILOT_LAB_E2E" not in os.environ, reason="live lab is not running")
def test_real_prometheus_and_loki_are_bounded() -> None:
    asyncio.run(_assert_real_prometheus_and_loki_are_bounded())


async def _assert_real_prometheus_and_loki_are_bounded() -> None:
    end = datetime.now(UTC)
    start = end - timedelta(minutes=5)
    metrics = await PrometheusMetricsAdapter(
        HttpxJsonClient("http://127.0.0.1:19090", timeout_seconds=5)
    ).query(
        MetricQuery(
            metric_kind=MetricKind.SERVICE_UP,
            service="web-01",
            environment="lab",
            start=start,
            end=end,
            step_seconds=15,
        )
    )
    assert len(metrics.series) <= 20
    logs = await LokiLogsAdapter(
        HttpxJsonClient("http://127.0.0.1:13100", timeout_seconds=5)
    ).query(LogQuery(service="web-01", environment="lab", start=start, end=end, limit=20))
    assert len(logs.entries) <= 20
    assert all(set(entry.labels) <= {"service", "environment", "level"} for entry in logs.entries)
