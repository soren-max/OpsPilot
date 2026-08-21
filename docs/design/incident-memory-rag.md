# Historical Incident Memory / RAG

M6 projects only resolved or closed incidents with a diagnosis into an
`IncidentKnowledgeRecord`. The projection is deterministic and excludes raw logs, prompts,
secrets, hidden reasoning, and checkpoint blobs.

```text
Incident DB -> IncidentMemoryIndexer -> EmbeddingProvider -> Qdrant
Current Incident -> KnowledgeQueryBuilder -> KnowledgeRetriever -> Investigator
```

The Qdrant adapter owns its URL, collection, named vector schema, and filters. Each point ID is a
UUIDv5 of `incident_id:knowledge_schema_version`, so repeated indexing is an upsert. Payloads track
the schema, embedding provider/model/version, and indexing time.

The collection has a cosine `dense` vector and an IDF-modified `sparse` vector. Retrieval uses two
prefetches and Qdrant reciprocal-rank fusion (RRF); dense and sparse scores are never added. Typed
queries allow service, environment, severity, and tags, but never raw vectors, collection names,
filters, or backend URLs.

## Evidence and knowledge

CURRENT EVIDENCE is a current observation and may ground a diagnosis. HISTORICAL KNOWLEDGE is an
untrusted precedent that may suggest a hypothesis. It never proves the current root cause,
authorizes an action, changes policy, or bypasses approval. A mutating proposal still requires at
least one valid current Evidence ID. Graph checkpoints store knowledge IDs only.

Indexing is explicit (`make memory-index`); web requests never trigger bulk indexing. The offline
default uses a versioned deterministic hash embedding for CI and demonstration. A production-grade
embedding provider remains an operator-selected future integration behind the same port.

## Evaluation

`make memory-eval` evaluates 40 synthetic resolved incidents and 12 queries across dense-only,
sparse-only, and Hybrid RRF. It writes JSON and a human-readable table with Recall@5, Recall@10,
MRR, root-cause hit rate, and latency. This fixture validates mechanics and regression behavior;
it is not a claim of production retrieval quality.
