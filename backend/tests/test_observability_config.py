from opentelemetry import trace

from app import observability


def test_otlp_is_optional(monkeypatch: object) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)  # type: ignore[attr-defined]
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(observability, "_configured_provider", None)  # type: ignore[attr-defined]

    assert observability.configure_telemetry() is None


def test_exporter_initialization_failure_does_not_break_workflow_spans(monkeypatch: object) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://telemetry.invalid")  # type: ignore[attr-defined]
    monkeypatch.setattr(observability, "_configured_provider", None)  # type: ignore[attr-defined]

    def fail_exporter() -> object:
        raise RuntimeError("collector unavailable")

    monkeypatch.setattr(observability, "OTLPSpanExporter", fail_exporter)  # type: ignore[attr-defined]

    assert observability.configure_telemetry() is None
    with trace.get_tracer("test").start_as_current_span("incident.run"):
        pass
