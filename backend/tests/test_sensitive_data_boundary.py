import base64
import json
import logging
from datetime import UTC, datetime

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.ai.context import EvidenceContextBuilder
from app.application.incident_service import IncidentService
from app.application.workflow_service import WorkflowService
from app.core.logging import JsonFormatter
from app.domain.audit.models import AuditEventType
from app.domain.incidents.evidence import EvidenceType
from app.observability import record_safe_exception
from app.repositories.incidents import AuditEventRepository
from app.schemas_incidents import EvidenceCreate
from app.services.redaction import redact_text
from app.workflows.incident.investigator import (
    InvestigationContext,
    InvestigationEvidence,
)
from tests.workflows.test_incident_workflow import create_incident, mock_action_service

NOW = datetime(2026, 9, 21, tzinfo=UTC)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _synthetic_jwt() -> str:
    return ".".join(
        (
            _base64url(b'{"alg":"none","typ":"JWT"}'),
            _base64url(b'{"sub":"synthetic-test-subject"}'),
            _base64url(b"synthetic-signature-not-cryptographic"),
        )
    )


def _synthetic_openai_style_key() -> str:
    alphabet = "".join(chr(ord("a") + index) for index in range(16))
    return "-".join(("sk", "live", alphabet))


def _synthetic_dsn() -> tuple[str, str]:
    password = "-".join(("synthetic", "dsn", "password"))
    authority = f"synthetic-user:{password}@db.example.test:5432/opspilot"
    return "://".join(("postgresql", authority)), password


def _synthetic_private_key() -> tuple[str, str]:
    label = " ".join(("RSA", "PRIVATE", "KEY"))
    material = "".join(("MII", "Synthetic", "KeyMaterial", "ForRedactionOnly"))
    block = "\n".join(
        (f"-----BEGIN {label}-----", material, f"-----END {label}-----")
    )
    return block, material


def _synthetic_slack_token() -> str:
    workspace = "".join(str(index % 10) for index in range(1, 13))
    token_body = "".join(chr(ord("a") + index) for index in range(16))
    return "-".join(("".join(("xox", "b")), workspace, token_body))


BARE_JWT = _synthetic_jwt()
BEARER_JWT = f"Authorization: Bearer {BARE_JWT}"
OPENAI_STYLE_KEY = _synthetic_openai_style_key()
API_KEY = f"api_key={OPENAI_STYLE_KEY}"
DSN, DSN_PASSWORD = _synthetic_dsn()
PEM, PEM_KEY_MATERIAL = _synthetic_private_key()
NESTED_SECRET = "-".join(("synthetic", "nested", "secret"))
NESTED_TOKEN = json.dumps({"config": {"db": {"token": NESTED_SECRET}}})
WEBHOOK = _synthetic_slack_token()
MULTILINE_PASSWORD = "-".join(("synthetic", "log", "password"))
MULTILINE = (
    "2026-09-21T00:00:00Z starting reconcile\n"
    f"2026-09-21T00:00:01Z password={MULTILINE_PASSWORD}\n"
    "2026-09-21T00:00:02Z done"
)

SECRET_PAIRS: list[tuple[str, str]] = [
    (BEARER_JWT, BARE_JWT),
    (BARE_JWT, BARE_JWT),
    (API_KEY, OPENAI_STYLE_KEY),
    (DSN, DSN_PASSWORD),
    (PEM, PEM_KEY_MATERIAL),
    (NESTED_TOKEN, NESTED_SECRET),
    (WEBHOOK, WEBHOOK),
    (MULTILINE, MULTILINE_PASSWORD),
]

SECRETS = [
    pytest.param(payload, secret, id=name)
    for name, (payload, secret) in zip(
        [
            "authorization-bearer-jwt",
            "standalone-jwt",
            "api-key",
            "database-dsn",
            "pem-private-key",
            "nested-json-token",
            "webhook-secret",
            "multiline-log",
        ],
        SECRET_PAIRS,
        strict=True,
    )
]


@pytest.mark.parametrize(("payload", "secret"), SECRETS)
def test_known_credential_shapes_are_redacted(payload: str, secret: str) -> None:
    redacted = redact_text(payload)

    assert redacted is not None
    assert secret not in redacted
    assert "[REDACTED" in redacted


@pytest.mark.parametrize(
    "value",
    [
        "8f14e45f-ceea-467a-9c1f-3b4a5c1d7e21",
        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "4bf92f3577b34da6a3ce929d0e0e4736",
        "web-01.production.internal",
        "incident-3c4d5e6f-7081-9203",
        "2026-09-21T00:00:00Z",
    ],
)
def test_ordinary_identifiers_survive_redaction(value: str) -> None:
    assert redact_text(value) == value


def add_evidence_with_secret(db: Session, incident_id: str) -> str:
    item = IncidentService(db).add_evidence(
        incident_id,
        EvidenceCreate(
            evidence_type=EvidenceType.LOG,
            source="loki",
            source_reference="https://logs.internal/query",
            summary=f"Provider error while running reconcile. {BEARER_JWT}",
            excerpt=f"{MULTILINE}\n{DSN}\n{PEM}",
            observed_at=NOW,
            collector="pytest",
            metadata={"entry_count": 3, "status": "down", "selected_values": [0, 1]},
        ),
        "tester",
    )
    return item.id


def test_evidence_is_sanitized_before_persistence(db: Session) -> None:
    incident_id = create_incident(db)
    evidence_id = add_evidence_with_secret(db, incident_id)

    item = IncidentService(db)._require(incident_id).evidence[0]
    stored = json.dumps(
        {
            "summary": item.summary,
            "excerpt": item.excerpt,
            "metadata": item.evidence_metadata,
            "source_reference": item.source_reference,
        }
    )

    assert item.id == evidence_id
    for _, secret in SECRET_PAIRS:
        assert secret not in stored
    # Non-secret, structured evidence fields are preserved.
    assert item.evidence_metadata["status"] == "down"
    assert item.evidence_metadata["selected_values"] == [0, 1]


def test_redaction_is_audited_without_recording_the_secret(db: Session) -> None:
    incident_id = create_incident(db)
    add_evidence_with_secret(db, incident_id)

    redaction_events = [
        event
        for event in AuditEventRepository(db).list_for_incident(incident_id)
        if event.event_type is AuditEventType.SENSITIVE_DATA_REDACTED
    ]

    assert redaction_events
    metadata = redaction_events[0].event_metadata
    assert "authorization_header" in str(metadata["redaction_type"])
    assert isinstance(metadata["count"], int)
    assert metadata["count"] >= 1
    rendered = json.dumps(metadata)
    for _, secret in SECRET_PAIRS:
        assert secret not in rendered


def test_secret_never_reaches_the_model_context(db: Session) -> None:
    incident_id = create_incident(db)
    add_evidence_with_secret(db, incident_id)
    item = IncidentService(db)._require(incident_id).evidence[0]

    request = EvidenceContextBuilder().build(
        InvestigationContext(
            incident_id=incident_id,
            service="web",
            environment="test",
            evidence=(
                InvestigationEvidence(
                    evidence_id=item.id,
                    evidence_type=item.evidence_type,
                    source=item.source,
                    observed_at=item.observed_at,
                    summary=item.summary,
                    excerpt=item.excerpt,
                    metadata=item.evidence_metadata,
                ),
            ),
        )
    )

    rendered = json.dumps(request.model_dump(mode="json"))
    for _, secret in SECRET_PAIRS:
        assert secret not in rendered


def test_secret_never_reaches_the_replay_snapshot(db: Session) -> None:
    incident_id = create_incident(db, "service unavailable")
    add_evidence_with_secret(db, incident_id)
    service = WorkflowService(
        db,
        checkpointer=InMemorySaver(),
        action_service=mock_action_service("mock-service"),
    )
    workflow = service.run(service.start(incident_id, "operator", "redaction-replay").id)

    rendered = json.dumps(workflow.state_references)
    for _, secret in SECRET_PAIRS:
        assert secret not in rendered


def test_secret_never_reaches_the_api_response(client: object, db: Session) -> None:
    incident_id = create_incident(db)
    add_evidence_with_secret(db, incident_id)

    response = client.get(f"/api/v1/incidents/{incident_id}")  # type: ignore[attr-defined]

    assert response.status_code == 200
    for _, secret in SECRET_PAIRS:
        assert secret not in response.text


def test_secret_never_reaches_logs() -> None:
    formatter = JsonFormatter()
    try:
        raise RuntimeError(f"provider rejected request with {BEARER_JWT} and {DSN}")
    except RuntimeError:
        import sys

        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="dispatch failed: %s",
            args=(API_KEY,),
            exc_info=sys.exc_info(),
        )

    rendered = formatter.format(record)

    assert "dispatch failed" in rendered
    for secret in (BARE_JWT, DSN_PASSWORD, OPENAI_STYLE_KEY):
        assert secret not in rendered
    assert "[REDACTED" in rendered


class RecordingSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}
        self.status: object | None = None
        self.recorded: list[BaseException] = []

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def set_status(self, status: object) -> None:
        self.status = status

    def record_exception(self, exc: BaseException, **kwargs: object) -> None:
        self.recorded.append(exc)


def test_exception_telemetry_records_no_secret_payload() -> None:
    span = RecordingSpan()
    record_safe_exception(span, RuntimeError(f"auth failed with {BEARER_JWT} at {DSN}"))  # type: ignore[arg-type]

    assert span.recorded == []
    assert span.attributes["exception.type"] == "RuntimeError"
    message = str(span.attributes["exception.message"])
    assert BARE_JWT not in message
    assert DSN_PASSWORD not in message
    assert "[REDACTED" in message
