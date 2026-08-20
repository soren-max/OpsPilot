import hashlib
from datetime import UTC, datetime

from app.adapters.http import JsonHttpClient
from app.capabilities.errors import CapabilityMalformedResponse
from app.capabilities.metrics import (
    MetricAggregation,
    MetricKind,
    MetricObservation,
    MetricPoint,
    MetricQuery,
    MetricSeries,
)

METRIC_EXPRESSIONS: dict[MetricKind, str] = {
    MetricKind.CPU_USAGE: "rate(process_cpu_seconds_total{%s}[5m])",
    MetricKind.MEMORY_USAGE: "process_resident_memory_bytes{%s}",
    MetricKind.REQUEST_RATE: "rate(http_requests_total{%s}[5m])",
    MetricKind.ERROR_RATE: (
        'rate(http_requests_total{%s,status=~"5.."}[5m]) '
        "/ rate(http_requests_total{%s}[5m])"
    ),
    MetricKind.LATENCY_P95: (
        "histogram_quantile(0.95, sum by (le) "
        "(rate(http_request_duration_seconds_bucket{%s}[5m])))"
    ),
    MetricKind.SERVICE_UP: "up{%s}",
}
AGGREGATIONS: dict[MetricAggregation, str] = {
    MetricAggregation.AVG: "avg",
    MetricAggregation.MAX: "max",
    MetricAggregation.SUM: "sum",
}


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_promql(query: MetricQuery) -> str:
    selectors = (
        f'service="{_escape_label(query.service)}",'
        f'environment="{_escape_label(query.environment)}"'
    )
    expression = METRIC_EXPRESSIONS[query.metric_kind].replace("%s", selectors)
    return f"{AGGREGATIONS[query.aggregation]}({expression})"


class PrometheusMetricsAdapter:
    def __init__(self, client: JsonHttpClient) -> None:
        self._client = client

    async def query(self, query: MetricQuery) -> MetricObservation:
        expression = render_promql(query)
        payload = await self._client.get_json(
            "/api/v1/query_range",
            params={
                "query": expression,
                "start": query.start.timestamp(),
                "end": query.end.timestamp(),
                "step": query.step_seconds,
            },
        )
        series = self._parse(payload, range_query=True)
        reference = self._reference(expression, query.start, query.end)
        return MetricObservation(
            query_kind=query.metric_kind,
            service=query.service,
            environment=query.environment,
            start=query.start,
            end=query.end,
            series=series,
            summary=f"{query.metric_kind.value} returned {len(series)} bounded series.",
            source_reference=reference,
            collected_at=datetime.now(UTC),
        )

    async def instant(
        self, query: MetricQuery, *, at: datetime | None = None
    ) -> MetricObservation:
        expression = render_promql(query)
        observed_at = at or query.end
        payload = await self._client.get_json(
            "/api/v1/query",
            params={"query": expression, "time": observed_at.timestamp()},
        )
        series = self._parse(payload, range_query=False)
        return MetricObservation(
            query_kind=query.metric_kind,
            service=query.service,
            environment=query.environment,
            start=observed_at,
            end=observed_at,
            series=series,
            summary=f"{query.metric_kind.value} returned {len(series)} bounded series.",
            source_reference=self._reference(expression, observed_at, observed_at),
            collected_at=datetime.now(UTC),
        )

    @staticmethod
    def _parse(payload: object, *, range_query: bool) -> tuple[MetricSeries, ...]:
        try:
            body = payload if isinstance(payload, dict) else {}
            data = body["data"]
            expected = "matrix" if range_query else "vector"
            if body.get("status") != "success" or data["resultType"] != expected:
                raise ValueError
            result = data["result"]
            if not isinstance(result, list):
                raise ValueError
            parsed: list[MetricSeries] = []
            for raw_series in result:
                labels = raw_series.get("metric", {})
                values = raw_series.get("values") if range_query else [raw_series.get("value")]
                if not isinstance(labels, dict) or not isinstance(values, list):
                    raise ValueError
                points = tuple(
                    MetricPoint(
                        timestamp=datetime.fromtimestamp(float(raw[0]), UTC),
                        value=float(raw[1]),
                    )
                    for raw in values
                    if isinstance(raw, list) and len(raw) == 2
                )
                if len(points) != len(values):
                    raise ValueError
                parsed.append(
                    MetricSeries(
                        labels={
                            str(k): str(v)[:200]
                            for k, v in labels.items()
                            if str(k) in {"service", "environment", "instance"}
                        },
                        points=points,
                    )
                )
            return tuple(parsed)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise CapabilityMalformedResponse("Prometheus returned a malformed response") from exc

    @staticmethod
    def _reference(expression: str, start: datetime, end: datetime) -> str:
        canonical = f"{expression}|{start.isoformat()}|{end.isoformat()}"
        return f"prometheus:query:{hashlib.sha256(canonical.encode()).hexdigest()}"
