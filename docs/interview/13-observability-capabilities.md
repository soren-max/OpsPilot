# Observability Capabilities

## How does Prometheus integrate?

The Metrics port accepts `MetricQuery`, not PromQL. The adapter maps `MetricKind` to reviewed
templates and calls Prometheus's direct HTTP API. Direct integration avoids coupling investigation
semantics to Grafana dashboards, data-source IDs, or user sessions.

## How does Loki integrate?

The Logs port accepts exact service/environment selectors, an optional level, bounded literal
keywords, time range, and limit. The adapter constructs LogQL and calls Loki `query_range`.
Tenant/auth configuration remains operator-owned.

## Why not let an LLM write PromQL or LogQL?

Those languages can widen selectors, run expensive regex/range scans, and return uncontrolled
volumes. Typed queries let deterministic policy authorize meaning before an adapter renders syntax.

## What happens when logs are too large?

Policy caps range and entry count, the HTTP client caps response bytes, the adapter truncates each
excerpt, and normalization stores only bounded excerpts plus a source reference.

## What if a capability is down?

Timeout, unavailable, rejected, and malformed-response failures are distinct. Collection isolates
each source, audits a safe failure code, and continues with successful or pre-existing evidence.
