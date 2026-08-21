from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.incidents.knowledge import IncidentKnowledgeRecord


@dataclass(frozen=True)
class KnowledgeQuery:
    service: str
    environment: str
    symptoms: tuple[str, ...]
    evidence_summary: tuple[str, ...]
    limit: int = 5
    severity: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.service or not self.environment:
            raise ValueError("Knowledge query service and environment are required")
        if not 1 <= self.limit <= 10:
            raise ValueError("Knowledge query limit must be between 1 and 10")


@dataclass(frozen=True)
class RetrievedKnowledge:
    knowledge_id: str
    incident_id: str
    title: str
    service: str
    environment: str
    root_cause: str
    remediation: tuple[str, ...]
    verification: tuple[str, ...]
    retrieval_score: float
    source_reference: str
    resolved_at: datetime


class KnowledgeRetriever(Protocol):
    def retrieve(self, query: KnowledgeQuery) -> tuple[RetrievedKnowledge, ...]: ...


class IncidentMemoryStore(KnowledgeRetriever, Protocol):
    def ensure_collection(self) -> None: ...

    def upsert(self, record: IncidentKnowledgeRecord) -> None: ...


class DenseEmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    version: str
    dimensions: int

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...
