from __future__ import annotations

import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import Span, Status, StatusCode

from app.services.redaction import redact_text

logger = logging.getLogger(__name__)
_configured_provider: TracerProvider | None = None


def record_safe_exception(span: Span, exc: BaseException) -> None:
    """Record a failure without writing secret-bearing exception text into the trace.

    ``Span.record_exception`` copies ``str(exc)`` verbatim into ``exception.message``, so a
    provider error that echoes a header or DSN would leak the credential into telemetry.
    """

    span.set_attribute("exception.type", type(exc).__name__)
    message = redact_text(str(exc))
    if message:
        span.set_attribute("exception.message", message[:500])
    span.set_status(Status(StatusCode.ERROR))


def build_tracer_provider(exporter: SpanExporter) -> TracerProvider:
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "opspilot"),
                "service.version": "0.1.0",
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def configure_telemetry() -> TracerProvider | None:
    """Enable OTLP only when explicitly configured; local demo stays dependency-free."""

    global _configured_provider
    if _configured_provider is not None:
        return _configured_provider
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if not endpoint or os.getenv("OTEL_SDK_DISABLED", "").lower() == "true":
        return None
    try:
        exporter = OTLPSpanExporter()
        provider = build_tracer_provider(exporter)
        trace.set_tracer_provider(provider)
    except Exception:
        logger.exception("OpenTelemetry exporter initialization failed; continuing without export")
        return None
    _configured_provider = provider
    logger.info("OpenTelemetry OTLP trace export enabled")
    return provider


def shutdown_telemetry(provider: TracerProvider | None) -> None:
    if provider is None:
        return
    try:
        provider.shutdown()
    except Exception:
        logger.exception("OpenTelemetry exporter shutdown failed")
