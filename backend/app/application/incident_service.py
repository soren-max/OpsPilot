from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.base import utc_now
from app.domain.audit.models import ActorType, AuditEventType
from app.domain.incidents.knowledge import IncidentKnowledgeRecord
from app.domain.incidents.lifecycle import InvalidIncidentTransition, require_transition
from app.domain.incidents.models import IncidentStatus, JsonValue
from app.models import OperationRequest, OperationTask
from app.repositories.incident_models import (
    DiagnosisRecord,
    EvidenceRecord,
    HypothesisRecord,
    IncidentActionLinkRecord,
    IncidentAuditEventRecord,
    IncidentRecord,
)
from app.repositories.incidents import (
    AuditEventRepository,
    DiagnosisRepository,
    EvidenceRepository,
    HypothesisRepository,
    IncidentActionRepository,
    IncidentRepository,
)
from app.schemas_incidents import (
    DiagnosisCreate,
    EvidenceCreate,
    HypothesisCreate,
    IncidentCreate,
    TimelineItem,
    TimelineKind,
)
from app.services.redaction import redact_account, redact_text

AUDIT_METADATA_ALLOWLIST = frozenset(
    {
        "previous_status",
        "new_status",
        "severity",
        "service",
        "environment",
        "source",
        "source_reference",
        "evidence_type",
        "evidence_id",
        "hypothesis_id",
        "diagnosis_id",
        "task_id",
        "action_fingerprint",
        "expected_version",
        "new_version",
        "reference",
        "workflow_id",
        "node",
        "duration_ms",
        "result_status",
        "investigator_mode",
        "provider",
        "model",
        "prompt_version",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "mcp_client",
        "mcp_tool",
        "trace_id",
        "execution_id",
        "backend_type",
        "backend_profile",
        "provider_execution_id",
        "approval_id",
    }
)


def safe_audit_metadata(values: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Allow only intentionally modeled, scalar audit fields."""
    result: dict[str, JsonValue] = {}
    for key, value in values.items():
        if key not in AUDIT_METADATA_ALLOWLIST:
            continue
        if isinstance(value, (dict, list)):
            continue
        result[key] = redact_text(value) if isinstance(value, str) else value
    return result


class IncidentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.incidents = IncidentRepository(db)
        self.evidence = EvidenceRepository(db)
        self.hypotheses = HypothesisRepository(db)
        self.diagnoses = DiagnosisRepository(db)
        self.audits = AuditEventRepository(db)
        self.actions = IncidentActionRepository(db)

    def create_incident(
        self, body: IncidentCreate, actor: str, correlation_id: str | None = None
    ) -> IncidentRecord:
        now = utc_now()
        item = IncidentRecord(
            title=body.title,
            summary=body.summary,
            severity=body.severity,
            status=IncidentStatus.OPEN,
            environment=body.environment,
            service=body.service,
            source=body.source,
            created_by=actor,
            tags=body.tags,
            version=1,
            created_at=now,
            updated_at=now,
        )
        try:
            self.incidents.add(item)
            self.db.flush()
            self._audit(
                item.id,
                AuditEventType.INCIDENT_CREATED,
                actor,
                "Incident created",
                correlation_id,
                {
                    "severity": body.severity.value,
                    "service": body.service,
                    "environment": body.environment,
                },
                occurred_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._require(item.id)

    def add_evidence(
        self,
        incident_id: str,
        body: EvidenceCreate,
        actor: str,
        correlation_id: str | None = None,
    ) -> EvidenceRecord:
        incident = self._require_mutable(incident_id)
        fingerprint = self._evidence_fingerprint(body)
        existing = self.evidence.find_by_fingerprint(incident_id, fingerprint)
        if existing is not None:
            return existing
        now = utc_now()
        item = EvidenceRecord(
            incident_id=incident.id,
            evidence_type=body.evidence_type,
            source=body.source,
            source_reference=body.source_reference,
            summary=body.summary,
            excerpt=body.excerpt,
            observed_at=body.observed_at,
            collected_at=now,
            collector=body.collector,
            evidence_metadata=body.metadata,
            fingerprint=fingerprint,
        )
        try:
            self.evidence.add(item)
            self.db.flush()
            self._audit(
                incident.id,
                AuditEventType.EVIDENCE_ADDED,
                actor,
                "Evidence added",
                correlation_id,
                {
                    "evidence_id": item.id,
                    "evidence_type": body.evidence_type.value,
                    "source": body.source,
                    "source_reference": body.source_reference,
                },
                occurred_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return item

    def add_hypothesis(
        self,
        incident_id: str,
        body: HypothesisCreate,
        actor: str,
        correlation_id: str | None = None,
    ) -> HypothesisRecord:
        incident = self._require_mutable(incident_id)
        self._validate_evidence_ids(
            incident_id, body.supporting_evidence_ids + body.contradicting_evidence_ids
        )
        now = utc_now()
        item = HypothesisRecord(
            incident_id=incident.id,
            statement=body.statement,
            confidence=body.confidence,
            status=body.status,
            supporting_evidence_ids=body.supporting_evidence_ids,
            contradicting_evidence_ids=body.contradicting_evidence_ids,
            created_at=now,
            created_by=actor,
        )
        try:
            self.hypotheses.add(item)
            self.db.flush()
            self._audit(
                incident.id,
                AuditEventType.HYPOTHESIS_ADDED,
                actor,
                "Hypothesis added",
                correlation_id,
                {"hypothesis_id": item.id},
                occurred_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return item

    def record_diagnosis(
        self,
        incident_id: str,
        body: DiagnosisCreate,
        actor: str,
        correlation_id: str | None = None,
    ) -> DiagnosisRecord:
        incident = self._require_mutable(incident_id)
        self._validate_evidence_ids(incident_id, body.evidence_ids)
        now = utc_now()
        item = DiagnosisRecord(
            incident_id=incident.id,
            root_cause=body.root_cause,
            contributing_factors=body.contributing_factors,
            evidence_ids=body.evidence_ids,
            confidence=body.confidence,
            created_by=actor,
            created_at=now,
        )
        try:
            self.diagnoses.add(item)
            self.db.flush()
            self._audit(
                incident.id,
                AuditEventType.DIAGNOSIS_RECORDED,
                actor,
                "Diagnosis recorded",
                correlation_id,
                {"diagnosis_id": item.id},
                occurred_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return item

    def transition(
        self,
        incident_id: str,
        target: IncidentStatus,
        expected_version: int,
        actor: str,
        correlation_id: str | None = None,
    ) -> IncidentRecord:
        item = self._require(incident_id)
        if item.version != expected_version:
            raise ConflictError(
                "INCIDENT_VERSION_CONFLICT",
                "Incident changed since it was read",
                {"expected_version": expected_version, "actual_version": item.version},
            )
        try:
            require_transition(item.status, target)
        except InvalidIncidentTransition as exc:
            raise ConflictError("INVALID_INCIDENT_TRANSITION", str(exc)) from exc
        now = utc_now()
        try:
            changed = self.incidents.compare_and_set_lifecycle(
                incident_id, expected_version, target, now
            )
            if not changed:
                raise ConflictError(
                    "INCIDENT_VERSION_CONFLICT", "Incident changed concurrently"
                )
            event_type = AuditEventType.INCIDENT_STATE_CHANGED
            if target is IncidentStatus.RESOLVED:
                event_type = AuditEventType.INCIDENT_RESOLVED
            elif target is IncidentStatus.CLOSED:
                event_type = AuditEventType.INCIDENT_CLOSED
            self._audit(
                incident_id,
                event_type,
                actor,
                f"Incident state changed from {item.status.value} to {target.value}",
                correlation_id,
                {
                    "previous_status": item.status.value,
                    "new_status": target.value,
                    "expected_version": expected_version,
                    "new_version": expected_version + 1,
                },
                occurred_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.expire_all()
        return self._require(incident_id)

    def resolve(
        self, incident_id: str, expected_version: int, actor: str, correlation_id: str | None = None
    ) -> IncidentRecord:
        return self.transition(
            incident_id, IncidentStatus.RESOLVED, expected_version, actor, correlation_id
        )

    def close(
        self, incident_id: str, expected_version: int, actor: str, correlation_id: str | None = None
    ) -> IncidentRecord:
        return self.transition(
            incident_id, IncidentStatus.CLOSED, expected_version, actor, correlation_id
        )

    def link_action(
        self,
        incident_id: str,
        task_id: str,
        action_fingerprint: str,
        actor: str,
        correlation_id: str | None = None,
    ) -> IncidentActionLinkRecord:
        incident = self._require_mutable(incident_id)
        if self.db.get(OperationTask, task_id) is None:
            raise NotFoundError("Operation task does not exist")
        now = utc_now()
        link = IncidentActionLinkRecord(
            incident_id=incident.id,
            task_id=task_id,
            action_fingerprint=action_fingerprint,
            created_at=now,
        )
        try:
            self.actions.add(link)
            self._audit(
                incident.id,
                AuditEventType.ACTION_PROPOSED,
                actor,
                "Action associated with incident",
                correlation_id,
                {"task_id": task_id, "action_fingerprint": action_fingerprint},
                occurred_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return link

    def timeline(self, incident_id: str) -> list[TimelineItem]:
        incident = self._require(incident_id)
        items = [
            TimelineItem(
                id=event.event_id,
                kind=(
                    TimelineKind.WORKFLOW
                    if event.event_type.value.startswith("WORKFLOW_")
                    else TimelineKind.INCIDENT
                ),
                event_type=event.event_type.value,
                occurred_at=event.occurred_at,
                summary=event.payload_summary,
                metadata=event.event_metadata,
            )
            for event in self.audits.list_for_incident(incident_id)
        ]
        items.extend(
            TimelineItem(
                id=value.id,
                kind=TimelineKind.EVIDENCE,
                event_type="EVIDENCE_OBSERVED",
                occurred_at=value.observed_at,
                summary=value.summary,
                reference_id=value.source_reference,
                metadata={"evidence_type": value.evidence_type.value},
            )
            for value in incident.evidence
        )
        items.extend(
            TimelineItem(
                id=value.id,
                kind=TimelineKind.HYPOTHESIS,
                event_type="HYPOTHESIS_RECORDED",
                occurred_at=value.created_at,
                summary=value.statement,
                metadata={"status": value.status.value, "confidence": value.confidence},
            )
            for value in incident.hypotheses
        )
        items.extend(
            TimelineItem(
                id=value.id,
                kind=TimelineKind.DIAGNOSIS,
                event_type="DIAGNOSIS_RECORDED",
                occurred_at=value.created_at,
                summary=value.root_cause,
                metadata={"confidence": value.confidence},
            )
            for value in incident.diagnoses
        )
        for link in incident.actions:
            task = self.db.get(OperationTask, link.task_id)
            summary = f"{task.action.value} action" if task is not None else "Linked action"
            items.append(
                TimelineItem(
                    id=f"action:{link.task_id}",
                    kind=TimelineKind.ACTION,
                    event_type="ACTION_LINKED",
                    occurred_at=link.created_at,
                    summary=summary,
                    reference_id=link.task_id,
                    metadata={"action_fingerprint": link.action_fingerprint},
                )
            )
            if task is not None and task.finished_at is not None:
                items.append(
                    TimelineItem(
                        id=f"verification:{link.task_id}",
                        kind=TimelineKind.VERIFICATION,
                        event_type="ACTION_FINISHED",
                        occurred_at=task.finished_at,
                        summary=f"Action finished with {task.status.value}",
                        reference_id=link.task_id,
                    )
                )
            if task is not None and task.operation_request_id is not None:
                request = self.db.get(OperationRequest, task.operation_request_id)
                if request is not None:
                    items.extend(
                        TimelineItem(
                            id=f"approval:{record.id}",
                            kind=TimelineKind.APPROVAL,
                            event_type=f"APPROVAL_{record.decision.value}",
                            occurred_at=record.created_at,
                            summary=f"Action approval {record.decision.value.lower()}",
                            reference_id=request.id,
                        )
                        for record in request.approval_records
                    )
        return sorted(items, key=lambda value: (value.occurred_at, value.id))

    def build_knowledge_record(self, incident_id: str) -> IncidentKnowledgeRecord:
        incident = self._require(incident_id)
        if incident.status not in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
            raise ConflictError(
                "INCIDENT_NOT_RESOLVED", "Only resolved incidents can become knowledge records"
            )
        if not incident.diagnoses or incident.resolved_at is None:
            raise ConflictError(
                "DIAGNOSIS_REQUIRED", "A resolved incident requires a diagnosis projection"
            )
        diagnosis = sorted(incident.diagnoses, key=lambda item: (item.created_at, item.id))[-1]
        tasks = [self.db.get(OperationTask, link.task_id) for link in incident.actions]
        remediation = tuple(
            sorted({task.action.value for task in tasks if task is not None})
        )
        verification = tuple(
            sorted(
                {
                    f"{task.id}:{task.status.value}"
                    for task in tasks
                    if task is not None and task.finished_at is not None
                }
            )
        )
        evidence = sorted(incident.evidence, key=lambda item: (item.observed_at, item.id))
        return IncidentKnowledgeRecord(
            incident_id=incident.id,
            title=incident.title,
            service=incident.service,
            environment=incident.environment,
            severity=incident.severity.value,
            symptoms=(incident.summary,),
            evidence_summary=tuple(item.summary for item in evidence),
            root_cause=diagnosis.root_cause,
            contributing_factors=tuple(diagnosis.contributing_factors),
            remediation=remediation,
            verification=verification,
            tags=tuple(sorted(incident.tags)),
            resolved_at=incident.resolved_at,
        )

    def _audit(
        self,
        incident_id: str,
        event_type: AuditEventType,
        actor: str,
        summary: str,
        correlation_id: str | None,
        metadata: dict[str, JsonValue],
        *,
        occurred_at: datetime,
    ) -> None:
        self.audits.append(
            IncidentAuditEventRecord(
                incident_id=incident_id,
                event_type=event_type,
                actor_type=ActorType.HUMAN,
                actor_id=redact_account(actor),
                correlation_id=correlation_id or str(uuid.uuid4()),
                occurred_at=occurred_at,
                payload_summary=redact_text(summary) or "Incident event",
                event_metadata=safe_audit_metadata(metadata),
            )
        )

    def _require(self, incident_id: str) -> IncidentRecord:
        item = self.incidents.get(incident_id)
        if item is None:
            raise NotFoundError("Incident does not exist")
        return item

    def _require_mutable(self, incident_id: str) -> IncidentRecord:
        item = self._require(incident_id)
        if item.status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
            raise ConflictError("INCIDENT_IMMUTABLE", "Resolved incidents cannot be mutated")
        return item

    def _validate_evidence_ids(self, incident_id: str, evidence_ids: list[str]) -> None:
        known = {item.id for item in self._require(incident_id).evidence}
        unknown = sorted(set(evidence_ids) - known)
        if unknown:
            raise ValidationError("Evidence references must belong to the incident", unknown)

    @staticmethod
    def _evidence_fingerprint(body: EvidenceCreate) -> str:
        canonical = json.dumps(
            body.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode()).hexdigest()
