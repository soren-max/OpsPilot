from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.application.incident_service import IncidentService
from app.core.errors import ConflictError
from app.domain.incidents.memory import IncidentMemoryStore, KnowledgeQuery
from app.repositories.incidents import IncidentRepository


@dataclass(frozen=True)
class IndexingResult:
    indexed: int
    embedding_version: str
    indexed_at: datetime


class IncidentMemoryIndexer:
    def __init__(self, db: Session, store: IncidentMemoryStore, embedding_version: str) -> None:
        self.db = db
        self.store = store
        self.embedding_version = embedding_version

    def index_one(self, incident_id: str) -> IndexingResult:
        record = IncidentService(self.db).build_knowledge_record(incident_id)
        self.store.ensure_collection()
        self.store.upsert(record)
        return IndexingResult(1, self.embedding_version, datetime.now(UTC))

    def index_all(self) -> IndexingResult:
        incidents, _ = IncidentRepository(self.db).list(limit=1_000_000)
        eligible = [item for item in incidents if item.status.value in {"RESOLVED", "CLOSED"}]
        self.store.ensure_collection()
        count = 0
        for incident in eligible:
            try:
                self.store.upsert(IncidentService(self.db).build_knowledge_record(incident.id))
            except ConflictError as exc:
                if exc.code in {"DIAGNOSIS_REQUIRED", "INCIDENT_NOT_RESOLVED"}:
                    continue
                raise
            count += 1
        return IndexingResult(count, self.embedding_version, datetime.now(UTC))


class KnowledgeQueryBuilder:
    def __init__(self, limit: int = 5) -> None:
        self.limit = limit

    def build(
        self,
        *,
        service: str,
        environment: str,
        symptoms: tuple[str, ...],
        evidence_summary: tuple[str, ...],
        severity: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> KnowledgeQuery:
        return KnowledgeQuery(
            service=service,
            environment=environment,
            symptoms=symptoms[:5],
            evidence_summary=evidence_summary[:10],
            limit=self.limit,
            severity=severity,
            tags=tuple(sorted(tags)),
        )


def query_text(query: KnowledgeQuery) -> str:
    parts = [f"service: {query.service}", f"environment: {query.environment}"]
    if query.symptoms:
        parts.append("symptoms: " + " | ".join(query.symptoms))
    if query.evidence_summary:
        parts.append("evidence_summary: " + " | ".join(query.evidence_summary))
    if query.severity:
        parts.append(f"severity: {query.severity}")
    if query.tags:
        parts.append("tags: " + " | ".join(query.tags))
    return "\n".join(parts)
