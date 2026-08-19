from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session, selectinload

from app.domain.incidents.models import IncidentStatus, Severity
from app.repositories.incident_models import (
    DiagnosisRecord,
    EvidenceRecord,
    HypothesisRecord,
    IncidentActionLinkRecord,
    IncidentAuditEventRecord,
    IncidentRecord,
)


class IncidentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, incident: IncidentRecord) -> None:
        self.db.add(incident)

    def get(self, incident_id: str) -> IncidentRecord | None:
        return self.db.scalar(self._query().where(IncidentRecord.id == incident_id))

    def list(
        self,
        *,
        status: IncidentStatus | None = None,
        severity: Severity | None = None,
        service: str | None = None,
        environment: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        tags: tuple[str, ...] = (),
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[IncidentRecord], int]:
        query = self._query()
        if status is not None:
            query = query.where(IncidentRecord.status == status)
        if severity is not None:
            query = query.where(IncidentRecord.severity == severity)
        if service is not None:
            query = query.where(IncidentRecord.service == service)
        if environment is not None:
            query = query.where(IncidentRecord.environment == environment)
        if created_from is not None:
            query = query.where(IncidentRecord.created_at >= created_from)
        if created_to is not None:
            query = query.where(IncidentRecord.created_at <= created_to)
        # JSON containment differs across supported engines, so tags are narrowed
        # deterministically after all portable SQL predicates are applied.
        items = list(self.db.scalars(query.order_by(IncidentRecord.created_at.desc())))
        if tags:
            required = set(tags)
            items = [item for item in items if required.issubset(item.tags)]
        return items[offset : offset + limit], len(items)

    def compare_and_set_lifecycle(
        self,
        incident_id: str,
        expected_version: int,
        target: IncidentStatus,
        changed_at: datetime,
    ) -> bool:
        values: dict[str, object] = {
            "status": target,
            "version": expected_version + 1,
            "updated_at": changed_at,
        }
        if target is IncidentStatus.RESOLVED:
            values["resolved_at"] = changed_at
        if target is IncidentStatus.CLOSED:
            values["closed_at"] = changed_at
        result = self.db.execute(
            update(IncidentRecord)
            .where(
                IncidentRecord.id == incident_id,
                IncidentRecord.version == expected_version,
            )
            .values(**values)
        )
        return bool(result.rowcount == 1)  # type: ignore[attr-defined]

    @staticmethod
    def _query() -> Select[tuple[IncidentRecord]]:
        return (
            select(IncidentRecord)
            .options(
                selectinload(IncidentRecord.evidence),
                selectinload(IncidentRecord.hypotheses),
                selectinload(IncidentRecord.diagnoses),
                selectinload(IncidentRecord.actions),
            )
            .execution_options(populate_existing=True)
        )


class EvidenceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_fingerprint(self, incident_id: str, fingerprint: str) -> EvidenceRecord | None:
        return self.db.scalar(
            select(EvidenceRecord).where(
                EvidenceRecord.incident_id == incident_id,
                EvidenceRecord.fingerprint == fingerprint,
            )
        )

    def add(self, evidence: EvidenceRecord) -> None:
        self.db.add(evidence)


class HypothesisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, hypothesis: HypothesisRecord) -> None:
        self.db.add(hypothesis)


class DiagnosisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, diagnosis: DiagnosisRecord) -> None:
        self.db.add(diagnosis)


class AuditEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, audit_event: IncidentAuditEventRecord) -> None:
        self.db.add(audit_event)

    def list_for_incident(self, incident_id: str) -> list[IncidentAuditEventRecord]:
        return list(
            self.db.scalars(
                select(IncidentAuditEventRecord)
                .where(IncidentAuditEventRecord.incident_id == incident_id)
                .order_by(IncidentAuditEventRecord.occurred_at, IncidentAuditEventRecord.event_id)
            )
        )


class IncidentActionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, link: IncidentActionLinkRecord) -> None:
        self.db.add(link)

    def list_for_incident(self, incident_id: str) -> list[IncidentActionLinkRecord]:
        return list(
            self.db.scalars(
                select(IncidentActionLinkRecord)
                .where(IncidentActionLinkRecord.incident_id == incident_id)
                .order_by(IncidentActionLinkRecord.created_at)
            )
        )
