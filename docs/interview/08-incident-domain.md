# Incident Domain

Status: **Implemented in M1C**

## Why is Evidence a first-class concept?

An incident decision is only defensible when its supporting observations retain type, source,
time, provenance, collector, and stable identity. A string buried in a prompt cannot be deduped,
contradicted, audited, or reused by a future workflow. First-class Evidence lets humans, tools,
and future Agents share the same contract without changing the schema.

## Why not store raw logs in the Incident database?

Logs and metric series are large, mutable operational datasets with their own retention and query
engines. OpsPilot stores a bounded excerpt, summary, fingerprint, typed metadata, and source
reference. Loki, Prometheus, or the ticket system remains the system of record.

## Why optimistic locking?

A user, worker, and future workflow may act on the same incident. A version compare-and-set turns
a lost update into an explicit `INCIDENT_VERSION_CONFLICT`; the caller must reload and reconsider
instead of silently overwriting a newer state.

## Why is status independent from LangGraph nodes?

`OPEN`, `INVESTIGATING`, `MITIGATING`, `VERIFYING`, `RESOLVED`, and `CLOSED` are durable business
facts. Workflow nodes are implementation details that can be split or reordered in M2 without a
database migration or API contract change.
