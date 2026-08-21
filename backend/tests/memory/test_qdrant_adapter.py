import os
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError

import pytest

from app.adapters.qdrant import QdrantIncidentMemory
from app.domain.incidents.knowledge import IncidentKnowledgeRecord
from app.domain.incidents.memory import KnowledgeQuery
from app.memory.embedding import DeterministicHashEmbedding


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


class RecordingQdrant(QdrantIncidentMemory):
    def __init__(self) -> None:
        super().__init__(
            "http://qdrant.test:6333",
            "operator_collection",
            DeterministicHashEmbedding(),
        )
        self.requests: list[tuple[str, str, dict[str, object] | None]] = []
        self.exists = False

    def _request(
        self, method: str, path: str, body: dict[str, object] | None = None
    ) -> dict[str, Any]:
        self.requests.append((method, path, body))
        if method == "GET" and not self.exists:
            raise HTTPError(path, 404, "not found", {}, None)
        if method == "PUT" and path == "/collections/operator_collection":
            self.exists = True
        if path.endswith("/points/query"):
            return {"result": {"points": []}}
        return {"result": {}}


def test_qdrant_schema_upsert_identity_filters_and_rrf_are_operator_owned() -> None:
    adapter = RecordingQdrant()
    adapter.ensure_collection()
    adapter.upsert(record())
    adapter.upsert(record())
    adapter.retrieve(
        KnowledgeQuery(
            service="web",
            environment="production",
            symptoms=("unavailable",),
            evidence_summary=("SERVICE_UP zero",),
            severity="HIGH",
            tags=("service-down",),
            limit=3,
        )
    )
    collection_body = adapter.requests[1][2]
    assert collection_body is not None
    assert set(collection_body["vectors"]) == {"dense"}  # type: ignore[arg-type]
    assert set(collection_body["sparse_vectors"]) == {"sparse"}  # type: ignore[arg-type]
    upserts = [body for method, path, body in adapter.requests if "/points?" in path]
    assert upserts[0] is not None and upserts[1] is not None
    first_point = upserts[0]["points"][0]  # type: ignore[index]
    second_point = upserts[1]["points"][0]  # type: ignore[index]
    assert first_point["id"] == second_point["id"] == record().knowledge_id
    query_body = adapter.requests[-1][2]
    assert query_body is not None
    assert query_body["query"] == {"fusion": "rrf"}
    assert len(query_body["prefetch"]) == 2  # type: ignore[arg-type]
    assert query_body["limit"] == 3


@pytest.mark.skipif(not os.getenv("OPSPILOT_MEMORY_E2E"), reason="requires local Qdrant")
def test_live_qdrant_hybrid_round_trip() -> None:
    adapter = QdrantIncidentMemory(
        os.getenv("OPSPILOT_QDRANT_BASE_URL", "http://127.0.0.1:16333"),
        "opspilot_test_incident_memory",
        DeterministicHashEmbedding(),
    )
    adapter.ensure_collection()
    adapter.upsert(record())
    results = adapter.retrieve(
        KnowledgeQuery(
            service="web",
            environment="production",
            symptoms=("health unreachable",),
            evidence_summary=("service up zero",),
            severity="HIGH",
            tags=("service-down",),
            limit=5,
        )
    )
    assert results
    assert results[0].incident_id == "incident-1"
    assert results[0].retrieval_score > 0
