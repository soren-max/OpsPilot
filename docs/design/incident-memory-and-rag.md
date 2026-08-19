# Incident Memory and RAG

Status: **M1C projection implemented; retrieval runtime planned for M6**

M1C deliberately stops at a deterministic `IncidentKnowledgeRecord`. It adds no embedding
library, vector database, RAGFlow dependency, or retrieval runtime.

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

## Future port

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

Planned candidate adapters:

- `QdrantHybridRetriever` — planned, not implemented.
- `RAGFlowKnowledgeAdapter` — planned, not implemented.

The domain does not select either backend. M6 must evaluate retrieval quality and enforce tenant,
environment, and service authorization before retrieved material reaches a workflow.
