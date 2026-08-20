# ADR 0006: Typed Observability Queries over Arbitrary Query Languages

## Status

Accepted for M3A.

## Context

PromQL and LogQL are powerful languages that can select broad datasets, use expensive ranges or
regular expressions, and expose labels an Incident investigator does not need. Letting a model or
API caller produce either language would combine reasoning with infrastructure authority and make
resource limits difficult to enforce.

Observability responses are also too large and volatile to serve as workflow state or durable
business truth. Future model conclusions must cite evidence that operators can trace back to the
source system.

## Decision

OpsPilot exposes typed domain-semantic queries (`MetricKind`, service health, bounded log and
ticket filters). Adapters own controlled PromQL/LogQL templates and operator-configured endpoints.
A central query policy enforces allowlists, windows, steps, series and result limits. Adapter
results normalize to bounded Incident Evidence with opaque provenance references; Graph State
stores only evidence IDs.

## Consequences

- Models and API callers cannot execute arbitrary PromQL, LogQL, URLs, labels, tenants, or headers.
- Read-only queries remain subject to availability and resource-consumption policy.
- New backend mappings require reviewed application code and deterministic tests.
- Raw logs and full metric payloads stay in their source systems, preventing prompt/context and DB
  growth.
- Some advanced ad hoc observability questions are intentionally unavailable until modeled as a
  safe typed capability.
