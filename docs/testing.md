# Testing Strategy

## M8 Governed Execution Plane

Execution tests cover strict backend contracts, deterministic routing, profile allowlists, Harness
trigger/status contracts, outbox uniqueness and `SKIP LOCKED` claims, expired-lease recovery,
indeterminate dispatch without retry, reconciliation, independent verification, architecture,
safe telemetry, API reads, and the frontend timeline. Real Harness credentials are not required.

## M7 MCP Capability Boundary

`backend/tests/mcp` covers official SDK discovery, schemas, structured tool calls, resources,
stdio and stateless Streamable HTTP black-box interop, auth rejection, scopes, fixed remote
mappings, poisoning containment, ownership defenses, and trace continuity. `make mcp-eval` reports
the versioned Agent Infrastructure Contract Eval without a model API or paid MCP service.

## M6 Historical Incident Memory

Memory tests cover deterministic projection and identity, idempotent Qdrant upsert, metadata
filters, a live hybrid round trip, workflow retrieval, and historical prompt-injection grounding.
`make memory-eval` evaluates 40 records and emits a table plus JSON without paid APIs or downloads.

## M5 Incident Lab

Normal CI keeps scenario parsing, safety invariants, architecture boundaries and mocked adapter
tests lightweight. A single isolated `lab-e2e` job starts Docker Compose once and validates the
real Prometheus/Loki/Health evidence path, PostgreSQL interrupt/resume, fixed Ansible remediation,
prompt-injection containment, reset and teardown. Run locally with `make lab-demo`; always use
`make demo-down` when inspecting a failed run.

## Local Demo Closeout

`make demo-doctor` performs read-only prerequisite and port checks. `make demo-local` resets the
controlled Compose project, waits for live readiness, and runs the canonical service-down lifecycle
with no paid dependency. The isolated `lab-e2e` CI job runs this command twice with a reset between
runs, proving startup, evidence collection, durable approval/resume, fixed Ansible remediation,
verification, cleanup, and repeatability. `make demo-full` keeps Memory and MCP available as an
optional advanced path; their existing contract jobs remain independent.

## Unit Tests

Domain model tests reject unknown actions, mismatched parameter schemas, unsafe identifiers, and
extra fields. Table-driven policy tests cover read-only, medium-risk, approval, and target rules.

## Integration Tests

Adapter tests verify fixed Action-to-Playbook mapping, generated variables, allowlists, and
post-action verification. Existing API, database, approval, and frontend tests protect the
deprecated migration baseline.

## Workflow Tests

M2 tests graph topology, JSON state, node routing, deterministic happy/blocked/waiting/failure
paths, idempotent replay, WorkflowRun persistence, audit trace, RBAC API behavior, and migration
round trips. Runtime integration tests prove that configured Mock and Ansible adapters are invoked,
the enabled Target allowlist and deterministic policy still gate execution, missing
`ActionService` fails closed, `WAITING_APPROVAL` never calls a mutating adapter, and execute-node
retries do not dispatch the same action twice. Architecture tests prevent Domain-to-LangGraph or
executor-implementation imports, direct Ansible/SQLAlchemy use in nodes, and implicit Mock imports
in workflow runtime. M4 adds durable approval interrupt/resume tests against a PostgreSQL
checkpointer.

M3A adds table-driven query-policy tests; controlled MetricKind-to-PromQL and LogQuery-to-LogQL
mapping tests; bounded response, timeout, provenance, partial-failure, and active collection tests.
M3B adds strict schema, evidence grounding, prompt-injection, provider failure/retry, evaluation
fixture, and workflow authorization-boundary tests. Default CI stays deterministic and uses mocked
HTTP transports; optional real-provider tests require explicit local opt-in and credentials.

## Security Tests

The current suite covers schema rejection, policy fail-closed behavior, output redaction, fixed
Ansible mappings, and the representative unsafe process-kill request. CI also runs a heuristic
secret scan and frontend dependency audit.

Future milestones add incident datasets, agent evaluation, adversarial safety evaluation, and
trace assertions.
