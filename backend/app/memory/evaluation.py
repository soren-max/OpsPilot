from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from app.memory.embedding import DeterministicHashEmbedding, tokenize


@dataclass(frozen=True)
class EvalDocument:
    incident_id: str
    root_cause_category: str
    text: str


@dataclass(frozen=True)
class EvalQuery:
    query_id: str
    text: str
    relevant_incident_ids: tuple[str, ...]
    expected_root_cause_category: str


@dataclass(frozen=True)
class RetrievalMetrics:
    retriever: str
    recall_at_5: float
    recall_at_10: float
    mrr: float
    root_cause_hit_rate: float
    latency_ms: float


def load_dataset(path: Path) -> tuple[tuple[EvalDocument, ...], tuple[EvalQuery, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = tuple(EvalDocument(**item) for item in payload["documents"])
    queries = tuple(
        EvalQuery(
            query_id=item["query_id"],
            text=item["text"],
            relevant_incident_ids=tuple(item["relevant_incident_ids"]),
            expected_root_cause_category=item["expected_root_cause_category"],
        )
        for item in payload["queries"]
    )
    return documents, queries


class OfflineRetrievalEvaluator:
    def __init__(self, documents: tuple[EvalDocument, ...]) -> None:
        self.documents = documents
        self.embedding = DeterministicHashEmbedding(128)
        self.document_vectors = self.embedding.embed(tuple(item.text for item in documents))

    def rank(self, query: str, mode: str) -> tuple[EvalDocument, ...]:
        dense = self._dense_ranks(query)
        sparse = self._sparse_ranks(query)
        if mode == "dense":
            ordered = dense
        elif mode == "sparse":
            ordered = sparse
        elif mode == "hybrid_rrf":
            dense_rank = {document.incident_id: rank for rank, document in enumerate(dense, 1)}
            sparse_rank = {document.incident_id: rank for rank, document in enumerate(sparse, 1)}
            ordered = tuple(
                sorted(
                    self.documents,
                    key=lambda item: -(
                        1 / (60 + dense_rank[item.incident_id])
                        + 1 / (60 + sparse_rank[item.incident_id])
                    ),
                )
            )
        else:
            raise ValueError("Retriever mode must be dense, sparse, or hybrid_rrf")
        return ordered

    def evaluate(self, queries: tuple[EvalQuery, ...], mode: str) -> RetrievalMetrics:
        recalls_5: list[float] = []
        recalls_10: list[float] = []
        reciprocal_ranks: list[float] = []
        root_cause_hits: list[float] = []
        latencies: list[float] = []
        for query in queries:
            started = time.perf_counter()
            ranked = self.rank(query.text, mode)
            latencies.append((time.perf_counter() - started) * 1000)
            relevant = set(query.relevant_incident_ids)
            top_5 = {item.incident_id for item in ranked[:5]}
            recalls_5.append(len(relevant & top_5) / len(relevant))
            recalls_10.append(
                len(relevant & {item.incident_id for item in ranked[:10]}) / len(relevant)
            )
            first = next(
                (rank for rank, item in enumerate(ranked, 1) if item.incident_id in relevant), 0
            )
            reciprocal_ranks.append(1 / first if first else 0)
            root_cause_hits.append(
                float(
                    any(
                        item.root_cause_category == query.expected_root_cause_category
                        for item in ranked[:5]
                    )
                )
            )
        return RetrievalMetrics(
            retriever=mode,
            recall_at_5=mean(recalls_5),
            recall_at_10=mean(recalls_10),
            mrr=mean(reciprocal_ranks),
            root_cause_hit_rate=mean(root_cause_hits),
            latency_ms=mean(latencies),
        )

    def _dense_ranks(self, query: str) -> tuple[EvalDocument, ...]:
        vector = self.embedding.embed((query,))[0]
        return tuple(
            item
            for _, item in sorted(
                zip(
                    (
                        sum(
                            left * right
                            for left, right in zip(vector, candidate, strict=True)
                        )
                        for candidate in self.document_vectors
                    ),
                    self.documents,
                    strict=True,
                ),
                key=lambda pair: (-pair[0], pair[1].incident_id),
            )
        )

    def _sparse_ranks(self, query: str) -> tuple[EvalDocument, ...]:
        query_tokens = set(tokenize(query))
        document_tokens = [set(tokenize(item.text)) for item in self.documents]
        document_frequency = {
            token: sum(token in tokens for tokens in document_tokens) for token in query_tokens
        }
        scores = []
        for item, tokens in zip(self.documents, document_tokens, strict=True):
            score = sum(
                math.log((len(self.documents) + 1) / (document_frequency[token] + 1))
                for token in query_tokens & tokens
            )
            scores.append((score, item))
        ordered = sorted(scores, key=lambda pair: (-pair[0], pair[1].incident_id))
        return tuple(item for _, item in ordered)
