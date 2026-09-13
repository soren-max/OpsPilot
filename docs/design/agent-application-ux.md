# Agent Application UX and Replay

M10/M11 add a presentation and observability layer without changing the frozen remediation or
GitOps graphs. The durable Incident domain, append-only AuditEvent rows, WorkflowRun metadata,
checkpoint, Approval, ExecutionRecord, and Outbox remain independent.

## Agent event projection

`GET /api/v1/incidents/{incident_id}/events` returns the stable read model:

```json
{
  "event_id": "uuid",
  "incident_id": "uuid",
  "event_type": "policy.evaluated",
  "stage": "POLICY",
  "timestamp": "2026-09-13T12:00:00Z",
  "status": "HUMAN_APPROVAL_REQUIRED",
  "data": {"policy_rule": "action.service_mutation"}
}
```

The projection translates existing AuditEvent types and workflow node metadata. It is not a second
event store. It exposes structured outcomes, IDs, actors, safe provider metadata, and timestamps;
it never exposes prompts, credentials, evidence bodies, checkpoints, or model chain-of-thought.

`GET /api/v1/incidents/{incident_id}/events/stream` serves the same projection as SSE. PostgreSQL
polling is deliberate: events remain durable, and the deployment needs no Redis or Kafka. The wire
format includes `id`, named `event`, and JSON `data`. `Last-Event-ID` resumes after the exact durable
AuditEvent cursor. Nginx buffering is disabled for `/api/`.

The console uses a small fetch-based SSE reader because OpsPilot stores its bearer token in browser
storage and native `EventSource` cannot set an Authorization header. It implements the same SSE
protocol and reconnect semantics without placing a bearer token in a query string.

## Frozen Evidence Replay

Each new workflow freezes a bounded replay manifest in internal WorkflowRun metadata after evidence
collection and historical retrieval. Current Evidence is frozen by immutable IDs pointing to the
durable Incident evidence rows. Historical results are copied into a bounded snapshot because the
Qdrant ranking and indexed payload may later change. The snapshot is omitted from ordinary workflow
API serialization.

`POST /api/v1/incidents/{incident_id}/replay` runs only:

```text
frozen inputs -> investigator -> grounding comparison -> deterministic policy
```

It does not invoke LangGraph resume, approval creation, ExecutionPlane, Outbox, Ansible, Harness, or
GitOps. The response compares original and replay diagnosis/action, reports grounding validity,
policy outcome, latency and available token usage, and always marks `no_side_effect: true`. The
default deterministic investigator works offline. `configured` mode uses only the provider/model
already selected by operator configuration; callers cannot provide arbitrary credentials or URLs.

Workflows created before the snapshot contract fail with `REPLAY_SNAPSHOT_UNAVAILABLE` instead of
accessing live Prometheus, Loki, Health, tickets, or Qdrant.

## OpenTelemetry and Langfuse

The API and worker initialize an OTLP/HTTP exporter only when `OTEL_EXPORTER_OTLP_ENDPOINT` or
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is present. Otherwise tracing remains an in-process no-op and
the local demo has no SaaS dependency. Exporter initialization and shutdown failure are isolated
from workflow outcomes.

The trace tree starts with `incident.run`; node spans cover evidence collection, memory retrieval,
investigation, grounding, policy, approval wait, execution, reconciliation, verification, and
finalization. Attributes are bounded identifiers and decision metadata. Raw prompts, raw evidence,
authorization headers, tokens, and credentials are excluded.

For Langfuse v4, configure the OTLP endpoint and Basic authorization in deployment secrets and add
`x-langfuse-ingestion-version=4` to the OTLP headers. No Langfuse token is stored in the repository.
