import hashlib
from datetime import UTC, datetime

from app.adapters.http import JsonHttpClient
from app.capabilities.errors import CapabilityMalformedResponse
from app.capabilities.logs import LogEntry, LogObservation, LogQuery


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_logql(query: LogQuery) -> str:
    expression = (
        f'{{service="{_escape(query.service)}",'
        f'environment="{_escape(query.environment)}"}}'
    )
    if query.severity is not None:
        expression += f' | level="{query.severity.value.lower()}"'
    for keyword in query.keywords:
        expression += f' |= "{_escape(keyword)}"'
    return expression


class LokiLogsAdapter:
    def __init__(
        self,
        client: JsonHttpClient,
        *,
        tenant: str | None = None,
        allowed_labels: frozenset[str] = frozenset(
            {"service", "environment", "level"}
        ),
    ) -> None:
        self._client = client
        self._tenant = tenant
        self._allowed_labels = allowed_labels

    async def query(self, query: LogQuery) -> LogObservation:
        expression = render_logql(query)
        headers = {"X-Scope-OrgID": self._tenant} if self._tenant else None
        payload = await self._client.get_json(
            "/loki/api/v1/query_range",
            params={
                "query": expression,
                "start": int(query.start.timestamp() * 1_000_000_000),
                "end": int(query.end.timestamp() * 1_000_000_000),
                "limit": query.limit,
                "direction": "backward",
            },
            headers=headers,
        )
        entries = self._parse(payload, query.limit, self._allowed_labels)
        reference = self._reference(expression, query.start, query.end)
        return LogObservation(
            service=query.service,
            environment=query.environment,
            start=query.start,
            end=query.end,
            entries=entries,
            summary=f"Loki returned {len(entries)} bounded log entries.",
            source_reference=reference,
            collected_at=datetime.now(UTC),
        )

    @staticmethod
    def _parse(
        payload: object, limit: int, allowed_labels: frozenset[str]
    ) -> tuple[LogEntry, ...]:
        try:
            body = payload if isinstance(payload, dict) else {}
            data = body["data"]
            if body.get("status") != "success" or data["resultType"] != "streams":
                raise ValueError
            streams = data["result"]
            if not isinstance(streams, list):
                raise ValueError
            entries: list[LogEntry] = []
            for stream in streams:
                labels = stream.get("stream", {})
                values = stream.get("values", [])
                if not isinstance(labels, dict) or not isinstance(values, list):
                    raise ValueError
                for raw in values:
                    if not isinstance(raw, list) or len(raw) != 2:
                        raise ValueError
                    timestamp = datetime.fromtimestamp(int(raw[0]) / 1_000_000_000, UTC)
                    excerpt = str(raw[1])[:1000]
                    reference = f"loki:entry:{hashlib.sha256(str(raw[0]).encode()).hexdigest()}"
                    entries.append(
                        LogEntry(
                            timestamp=timestamp,
                            level=str(labels.get("level", "unknown"))[:20],
                            message_excerpt=excerpt,
                            labels={
                                str(k): str(v)[:200]
                                for k, v in labels.items()
                                if str(k) in allowed_labels
                            },
                            source_reference=reference,
                        )
                    )
            entries.sort(key=lambda item: (item.timestamp, item.source_reference), reverse=True)
            return tuple(entries[:limit])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise CapabilityMalformedResponse("Loki returned a malformed response") from exc

    @staticmethod
    def _reference(expression: str, start: datetime, end: datetime) -> str:
        canonical = f"{expression}|{start.isoformat()}|{end.isoformat()}"
        return f"loki:query:{hashlib.sha256(canonical.encode()).hexdigest()}"
