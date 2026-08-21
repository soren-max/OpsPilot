from datetime import UTC, datetime

import pytest

from app.domain.incidents.knowledge import IncidentKnowledgeRecord
from app.domain.incidents.memory import KnowledgeQuery
from app.memory.embedding import DeterministicHashEmbedding
from app.memory.service import KnowledgeQueryBuilder


def record() -> IncidentKnowledgeRecord:
    return IncidentKnowledgeRecord(
        incident_id="incident-1",
        title="Web process unavailable",
        service="web",
        environment="production",
        severity="HIGH",
        symptoms=("health unreachable",),
        evidence_summary=("SERVICE_UP was zero",),
        root_cause="Service process unavailable",
        contributing_factors=(),
        remediation=("restart_service",),
        verification=("health restored",),
        tags=("service-down",),
        resolved_at=datetime(2026, 8, 20, tzinfo=UTC),
    )


def test_knowledge_identity_and_serialization_are_stable() -> None:
    first = record()
    second = record()
    assert first.knowledge_id == second.knowledge_id
    assert first.serialize() == second.serialize()
    assert "raw logs" not in first.retrieval_text()


def test_query_builder_is_typed_bounded_and_deterministic() -> None:
    query = KnowledgeQueryBuilder(limit=3).build(
        service="web",
        environment="production",
        symptoms=tuple(f"symptom-{index}" for index in range(10)),
        evidence_summary=tuple(f"evidence-{index}" for index in range(20)),
        tags=("z", "a"),
    )
    assert query.limit == 3
    assert len(query.symptoms) == 5
    assert len(query.evidence_summary) == 10
    assert query.tags == ("a", "z")
    with pytest.raises(TypeError):
        KnowledgeQuery(**{**query.__dict__, "collection": "caller-selected"})


def test_fake_embedding_is_offline_deterministic_and_versioned() -> None:
    provider = DeterministicHashEmbedding(32)
    assert provider.embed(("service unavailable",)) == provider.embed(("service unavailable",))
    assert provider.provider_name == "opspilot"
    assert provider.model_name == "deterministic-hash"
    assert provider.version == "1"
