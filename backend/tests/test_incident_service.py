from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.application.incident_service import IncidentService, safe_audit_metadata
from app.core.enums import OperationAction, OperationScope
from app.core.errors import ConflictError
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import IncidentStatus, Severity
from app.models import OperationTask
from app.repositories.incident_models import IncidentAuditEventRecord, IncidentRecord
from app.schemas_incidents import DiagnosisCreate, EvidenceCreate, IncidentCreate


def incident_body(**overrides: object) -> IncidentCreate:
    values: dict[str, object] = {
        "title": "Checkout latency",
        "summary": "Checkout latency exceeded the SLO",
        "severity": Severity.HIGH,
        "environment": "test-mock",
        "service": "checkout",
        "source": "operator",
        "tags": ["payments", "latency"],
    }
    values.update(overrides)
    return IncidentCreate.model_validate(values)


def evidence_body(observed_at: datetime | None = None) -> EvidenceCreate:
    return EvidenceCreate(
        evidence_type=EvidenceType.METRIC,
        source="prometheus",
        source_reference="prom://query/latency-p99",
        summary="p99 exceeded 2 seconds",
        excerpt="p99=2.4",
        observed_at=observed_at or datetime.now(UTC),
        collector="operator",
        metadata={"region": "west"},
    )


def test_evidence_is_deduplicated_by_stable_fingerprint(db: Session) -> None:
    service = IncidentService(db)
    incident = service.create_incident(incident_body(), "alice")
    observed_at = datetime.now(UTC)

    first = service.add_evidence(incident.id, evidence_body(observed_at), "alice")
    second = service.add_evidence(incident.id, evidence_body(observed_at), "alice")

    assert second.id == first.id
    assert len(service._require(incident.id).evidence) == 1


def test_optimistic_concurrency_rejects_stale_incident_version(db: Session) -> None:
    incident_id = IncidentService(db).create_incident(incident_body(), "alice").id
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False, class_=Session)
    with factory() as first, factory() as stale:
        assert stale.get(IncidentRecord, incident_id) is not None
        IncidentService(first).transition(
            incident_id, IncidentStatus.INVESTIGATING, 1, "alice"
        )
        with pytest.raises(ConflictError, match="changed") as raised:
            IncidentService(stale).transition(
                incident_id, IncidentStatus.INVESTIGATING, 1, "bob"
            )
        assert raised.value.code == "INCIDENT_VERSION_CONFLICT"


def test_incident_audit_event_rejects_update_and_delete(db: Session) -> None:
    incident = IncidentService(db).create_incident(incident_body(), "alice")
    event = db.query(IncidentAuditEventRecord).filter_by(incident_id=incident.id).one()

    event.payload_summary = "changed"
    with pytest.raises(ValueError, match="append-only"):
        db.commit()
    db.rollback()

    event = db.get(IncidentAuditEventRecord, event.event_id)
    assert event is not None
    db.delete(event)
    with pytest.raises(ValueError, match="append-only"):
        db.commit()
    db.rollback()


def test_audit_failure_rolls_back_incident_mutation(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = IncidentService(db)

    def fail_audit(_event: IncidentAuditEventRecord) -> None:
        raise RuntimeError("audit storage unavailable")

    monkeypatch.setattr(service.audits, "append", fail_audit)
    with pytest.raises(RuntimeError, match="audit storage unavailable"):
        service.create_incident(incident_body(), "alice")

    assert db.query(IncidentRecord).count() == 0


def test_audit_failure_rolls_back_versioned_state_change(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = IncidentService(db)
    incident = service.create_incident(incident_body(), "alice")

    def fail_audit(_event: IncidentAuditEventRecord) -> None:
        raise RuntimeError("audit storage unavailable")

    monkeypatch.setattr(service.audits, "append", fail_audit)
    with pytest.raises(RuntimeError, match="audit storage unavailable"):
        service.transition(incident.id, IncidentStatus.INVESTIGATING, 1, "alice")

    db.expire_all()
    unchanged = db.get(IncidentRecord, incident.id)
    assert unchanged is not None
    assert unchanged.status is IncidentStatus.OPEN
    assert unchanged.version == 1


def test_timeline_is_ordered_and_knowledge_serialization_is_deterministic(db: Session) -> None:
    service = IncidentService(db)
    incident = service.create_incident(incident_body(), "alice")
    evidence = service.add_evidence(
        incident.id, evidence_body(datetime.now(UTC) - timedelta(hours=1)), "alice"
    )
    service.record_diagnosis(
        incident.id,
        DiagnosisCreate(
            root_cause="A saturated connection pool",
            contributing_factors=["Traffic spike"],
            evidence_ids=[evidence.id],
            confidence=0.9,
        ),
        "alice",
    )
    investigating = service.transition(
        incident.id, IncidentStatus.INVESTIGATING, 1, "alice"
    )
    service.resolve(incident.id, investigating.version, "alice")

    timeline = service.timeline(incident.id)
    assert [item.occurred_at for item in timeline] == sorted(
        item.occurred_at for item in timeline
    )
    record = service.build_knowledge_record(incident.id)
    assert record.root_cause == "A saturated connection pool"
    assert record.serialize() == service.build_knowledge_record(incident.id).serialize()


def test_action_association_does_not_modify_action_request_model(db: Session) -> None:
    service = IncidentService(db)
    incident = service.create_incident(incident_body(), "alice")
    task = OperationTask(
        environment_id="00000000-0000-0000-0000-000000000001",
        action=OperationAction.STATUS,
        scope=OperationScope.ALL,
        requested_by="alice",
    )
    db.add(task)
    db.commit()

    link = service.link_action(incident.id, task.id, "a" * 64, "alice")

    assert link.task_id == task.id
    assert service._require(incident.id).actions[0].action_fingerprint == "a" * 64


def test_audit_metadata_uses_allowlist_and_redaction() -> None:
    result = safe_audit_metadata(
        {
            "source_reference": "ticket token=top-secret",
            "token": "top-secret",
            "reference": "credential=unsafe",
        }
    )

    assert "token" not in result
    assert result["source_reference"] == "ticket token=[REDACTED]"
    assert result["reference"] == "credential=[REDACTED]"
