import time

import httpx
from pydantic import ValidationError

from app.ai.errors import (
    LLMMalformedOutput,
    LLMPolicyViolation,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
)
from app.ai.models import (
    InvestigationModelOutput,
    InvestigationPromptInput,
    ModelUsage,
    StructuredReasoningResult,
)
from app.ai.prompts import build_messages

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIResponsesProvider:
    """OpenAI Responses adapter with strict JSON schema output and no tools."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        timeout_seconds: float,
        max_response_bytes: int = 256_000,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_name = model
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_seconds)
        self._max_response_bytes = max_response_bytes
        self._transport = transport

    async def generate_investigation(
        self, request: InvestigationPromptInput
    ) -> StructuredReasoningResult:
        started = time.monotonic()
        body = {
            "model": self.model_name,
            "input": build_messages(request),
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "investigation_result",
                    "strict": True,
                    "schema": InvestigationModelOutput.model_json_schema(),
                }
            },
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
                transport=self._transport,
            ) as client:
                response = await client.post(
                    OPENAI_RESPONSES_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeout("LLM provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable("LLM provider is unavailable") from exc
        if response.status_code == 429:
            raise LLMRateLimited("LLM provider rate limited the request")
        if response.status_code >= 500:
            raise LLMUnavailable("LLM provider is temporarily unavailable")
        if response.status_code >= 400:
            raise LLMUnavailable("LLM provider rejected the configured request")
        if len(response.content) > self._max_response_bytes:
            raise LLMMalformedOutput("LLM response exceeds the configured size limit")
        try:
            payload = response.json()
            if payload.get("status") != "completed":
                raise ValueError
            output_text = self._output_text(payload)
            output = InvestigationModelOutput.model_validate_json(output_text)
            usage_payload = payload.get("usage") or {}
            usage = ModelUsage(
                input_tokens=usage_payload.get("input_tokens"),
                output_tokens=usage_payload.get("output_tokens"),
            )
        except LLMPolicyViolation:
            raise
        except (AttributeError, KeyError, TypeError, ValueError, ValidationError) as exc:
            raise LLMMalformedOutput("LLM provider returned malformed structured output") from exc
        return StructuredReasoningResult(
            output=output,
            provider=self.provider_name,
            model=self.model_name,
            prompt_version=request.prompt_version,
            latency_ms=int((time.monotonic() - started) * 1000),
            usage=usage,
        )

    @staticmethod
    def _output_text(payload: dict[str, object]) -> str:
        output = payload.get("output")
        if not isinstance(output, list):
            raise ValueError
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "refusal":
                    raise LLMPolicyViolation("LLM provider refused the investigation request")
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    return str(part["text"])
        raise ValueError
