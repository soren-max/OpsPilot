# Incident Memory and RAG

Status: **Superseded by the implemented M6 design in `incident-memory-rag.md`**

This document records the earlier M1C projection boundary. M6 subsequently implemented the Qdrant
hybrid adapter, deterministic offline embedding, workflow retrieval, and evaluation. See
[`incident-memory-rag.md`](incident-memory-rag.md) for current behavior.

## Knowledge flow

```text
KnowledgeSource
   +-- Resolved Incident
   +-- SRE Playbook
   +-- Runbook
   +-- Postmortem
   +-- Operations Manual
              |
              v
       Retrieval Backend
              |
              v
      Retrieved Evidence
              |
              v
   LangGraph Investigation
```

Only `RESOLVED` and `CLOSED` incidents can produce an IncidentKnowledgeRecord. Open hypotheses
are provisional and must never be presented as trusted organizational memory. Projection fields
are stable and serialized deterministically: incident identity and scope, symptoms, curated
evidence summaries, diagnosis, contributing factors, remediation, verification, tags, and
resolution time. Raw log bodies stay in Loki, Prometheus, ticketing, or another source system and
are referenced by provenance.

## Original port sketch

```python
class KnowledgeRetriever(Protocol):
    def retrieve(
        self,
        query: str,
        service: str | None,
        environment: str | None,
        tags: tuple[str, ...],
        time_range: TimeRange | None,
        top_k: int,
    ) -> list[RetrievedEvidence]: ...
```

The port returns bounded, provenance-bearing evidence rather than an untyped text blob. Ranking,
hybrid search, authorization filters, freshness, and source trust remain adapter concerns.

Original candidate adapters:

- Qdrant hybrid retrieval — implemented in M6 behind the memory adapter boundary.
- RAGFlow adapter — not implemented and not part of Portfolio v1.0.

The domain does not select a backend. M6 evaluates retrieval quality and keeps retrieved historical
material distinct from evidence; deployment-specific authorization remains operator-owned.
