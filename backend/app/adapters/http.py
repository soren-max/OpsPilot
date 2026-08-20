from collections.abc import Mapping
from typing import Protocol

import httpx

from app.capabilities.errors import (
    CapabilityMalformedResponse,
    CapabilityTimeout,
    CapabilityUnavailable,
)


class JsonHttpClient(Protocol):
    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | float],
        headers: Mapping[str, str] | None = None,
    ) -> object: ...


class HttpxJsonClient:
    """Bounded JSON client for operator-configured observability endpoints."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        max_response_bytes: int = 1_000_000,
        default_headers: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = httpx.Timeout(timeout_seconds)
        self._limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        self._default_headers = dict(default_headers or {})
        self._transport = transport
        self._max_response_bytes = max_response_bytes

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | float],
        headers: Mapping[str, str] | None = None,
    ) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                limits=self._limits,
                headers=self._default_headers,
                transport=self._transport,
            ) as client:
                response = await client.get(path, params=params, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise CapabilityTimeout("Observability request timed out") from exc
        except httpx.HTTPError as exc:
            raise CapabilityUnavailable("Observability endpoint is unavailable") from exc
        if len(response.content) > self._max_response_bytes:
            raise CapabilityMalformedResponse("Observability response exceeds size limit")
        try:
            return response.json()
        except ValueError as exc:
            raise CapabilityMalformedResponse(
                "Observability endpoint returned invalid JSON"
            ) from exc
