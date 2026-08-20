import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.adapters.loki import LokiLogsAdapter
from app.adapters.prometheus import PrometheusMetricsAdapter
from app.core.config import Settings
from app.worker import build_action_service, build_incident_capabilities


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:password@prometheus.example.test",
        "https://prometheus.example.test?target=http://internal",
        "//prometheus.example.test",
    ],
)
def test_observability_base_urls_are_operator_validated(url: str) -> None:
    with pytest.raises(ValidationError, match="credential-free HTTP"):
        Settings(prometheus_base_url=url, _env_file=None)


def test_capability_secrets_are_masked_by_settings() -> None:
    token = "test-observability-token"
    settings = Settings(
        prometheus_base_url="https://prometheus.example.test",
        prometheus_auth_token=token,
        loki_base_url="https://loki.example.test",
        loki_auth_token=token,
        _env_file=None,
    )
    assert token not in repr(settings)
    assert settings.prometheus_auth_token is not None
    assert settings.prometheus_auth_token.get_secret_value() == token


def test_worker_bootstrap_injects_configured_observability_adapters(db: Session) -> None:
    settings = Settings(
        prometheus_base_url="https://prometheus.example.test",
        loki_base_url="https://loki.example.test",
        loki_tenant="tenant-a",
        _env_file=None,
    )
    capabilities = build_incident_capabilities(
        db, settings, build_action_service(db, settings)
    )
    assert isinstance(capabilities.metrics, PrometheusMetricsAdapter)
    assert isinstance(capabilities.logs, LokiLogsAdapter)
    assert capabilities.policy.allowed_services == frozenset(
        {"mock-service", "other-service"}
    )
