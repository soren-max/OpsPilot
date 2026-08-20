# Observability and Ticket Capabilities

## Scope

M3A lets the Incident Workflow actively collect bounded read-only evidence without introducing an
LLM, RAG, MCP, durable HITL, arbitrary query language, or an Incident Lab. The dependency direction
is `Workflow -> Capability Port <- Adapter`; Domain imports none of LangGraph, HTTPX, Prometheus,
Loki, ticket vendors, or MCP.

## Typed queries

`MetricQuery` expresses a stable `MetricKind`, service, environment, bounded time window, step, and
aggregation. `PrometheusMetricsAdapter` owns the only PromQL templates and supports the official
`/api/v1/query` and `/api/v1/query_range` response envelopes. No API or Agent field accepts raw
PromQL.

`LogQuery` expresses service, environment, severity, literal keywords, range, and limit.
`LokiLogsAdapter` owns the stream selector and literal filters sent to
`/loki/api/v1/query_range`. Tenant and authorization headers come only from operator settings.
The official APIs describe the endpoint and bounded parameters used here:
[Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/) and
[Loki HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/).

`TicketQuery` is vendor-neutral. M3A supplies a deterministic fixture-backed Mock adapter; Jira,
GitHub Issues, or ServiceNow adapters can implement the same port later without changing workflow
state. `HealthCapability` presents investigation semantics (`get_service_health`) even when its
adapter reuses the controlled read-only Action boundary.

## Query safety

`CapabilityQueryPolicy` rejects unknown services, excessive ranges, tiny metric steps, disallowed
metric kinds, excess series, excessive log/ticket limits, and unsafe keywords. Service and
environment selectors are strict identifiers. Query objects expose neither URL, tenant, headers,
nor arbitrary labels. Read-only means no mutation authority; it does not mean unlimited resource
consumption.

The shared HTTP client applies timeouts, connection limits, status validation, JSON validation,
and a response-byte ceiling. Errors are mapped to safe capability failures without including
authorization headers, cookies, tenant secrets, response bodies, or configured URLs.

## Evidence and provenance

Adapter observations are normalized as existing Incident Evidence:

- Prometheus -> `METRIC`
- Loki -> `LOG`
- Ticket -> `TICKET`
- Health -> `SERVICE_STATUS`

Evidence retains source, opaque source reference, observed and collected times, collector,
bounded summary/excerpt, selected safe metadata, and the M1C fingerprint. Raw metric responses and
large log bodies never enter Incident DB or Graph State. Stable workflow collection windows and
opaque references make node replay deduplicate through the existing Incident fingerprint.

## Workflow and failure handling

Worker bootstrap builds `IncidentCapabilities` from enabled Services and operator configuration,
then injects it into `WorkflowService`. `collect_context` concurrently gathers configured sources
with a per-capability timeout. Results are consumed in deterministic metrics/logs/tickets/health
order. One failure records a safe degraded audit event and preserves other evidence. LangGraph
state receives only the resulting evidence IDs.

M3A deliberately degrades when some or all external sources are unavailable; the deterministic
investigator can still use pre-existing Incident Evidence. Automated minimum-evidence policies are
deferred until their operational semantics are defined.
