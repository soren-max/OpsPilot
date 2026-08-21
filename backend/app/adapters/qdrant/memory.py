import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from app.domain.incidents.knowledge import IncidentKnowledgeRecord
from app.domain.incidents.memory import DenseEmbeddingProvider, KnowledgeQuery, RetrievedKnowledge
from app.memory.embedding import sparse_vector
from app.memory.service import query_text


class QdrantIncidentMemory:
    """Operator-configured Qdrant hybrid adapter; callers cannot supply backend query details."""

    def __init__(
        self,
        base_url: str,
        collection: str,
        embedding: DenseEmbeddingProvider,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.embedding = embedding
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener(ProxyHandler({}))

    def ensure_collection(self) -> None:
        try:
            self._request("GET", f"/collections/{self.collection}")
            return
        except HTTPError as exc:
            if exc.code != 404:
                raise
        self._request(
            "PUT",
            f"/collections/{self.collection}",
            {
                "vectors": {
                    "dense": {
                        "size": self.embedding.dimensions,
                        "distance": "Cosine",
                    }
                },
                "sparse_vectors": {"sparse": {"modifier": "idf"}},
            },
        )
        for field in ("incident_id", "service", "environment", "severity", "tags"):
            self._request(
                "PUT",
                f"/collections/{self.collection}/index",
                {"field_name": field, "field_schema": "keyword"},
            )

    def upsert(self, record: IncidentKnowledgeRecord) -> None:
        text = record.retrieval_text()
        dense = self.embedding.embed((text,))[0]
        indices, values = sparse_vector(text)
        now = datetime.now(UTC).isoformat()
        payload = {
            **record.model_dump(mode="json"),
            "knowledge_id": record.knowledge_id,
            "source_reference": f"/incidents/{record.incident_id}",
            "knowledge_schema_version": record.knowledge_schema_version,
            "embedding_provider": self.embedding.provider_name,
            "embedding_model": self.embedding.model_name,
            "embedding_version": self.embedding.version,
            "indexed_at": now,
        }
        self._request(
            "PUT",
            f"/collections/{self.collection}/points?wait=true",
            {
                "points": [
                    {
                        "id": record.knowledge_id,
                        "vector": {
                            "dense": list(dense),
                            "sparse": {"indices": list(indices), "values": list(values)},
                        },
                        "payload": payload,
                    }
                ]
            },
        )

    def retrieve(self, query: KnowledgeQuery) -> tuple[RetrievedKnowledge, ...]:
        text = query_text(query)
        dense = self.embedding.embed((text,))[0]
        indices, values = sparse_vector(text)
        must: list[dict[str, object]] = [
            {"key": "service", "match": {"value": query.service}},
            {"key": "environment", "match": {"value": query.environment}},
        ]
        if query.severity:
            must.append({"key": "severity", "match": {"value": query.severity}})
        for tag in query.tags:
            must.append({"key": "tags", "match": {"value": tag}})
        body = {
            "prefetch": [
                {"query": list(dense), "using": "dense", "limit": query.limit * 4},
                {
                    "query": {"indices": list(indices), "values": list(values)},
                    "using": "sparse",
                    "limit": query.limit * 4,
                },
            ],
            "query": {"fusion": "rrf"},
            "filter": {"must": must},
            "limit": query.limit,
            "with_payload": True,
        }
        response = self._request("POST", f"/collections/{self.collection}/points/query", body)
        points = response.get("result", {}).get("points", [])
        return tuple(self._result(item) for item in points)

    def _result(self, item: dict[str, Any]) -> RetrievedKnowledge:
        payload = item["payload"]
        return RetrievedKnowledge(
            knowledge_id=str(payload["knowledge_id"]),
            incident_id=str(payload["incident_id"]),
            title=str(payload["title"]),
            service=str(payload["service"]),
            environment=str(payload["environment"]),
            root_cause=str(payload["root_cause"]),
            remediation=tuple(str(value) for value in payload.get("remediation", [])),
            verification=tuple(str(value) for value in payload.get("verification", [])),
            retrieval_score=float(item["score"]),
            source_reference=str(payload["source_reference"]),
            resolved_at=datetime.fromisoformat(str(payload["resolved_at"])),
        )

    def _request(
        self, method: str, path: str, body: dict[str, object] | None = None
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        request = Request(
            self.base_url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        with self._opener.open(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read())
