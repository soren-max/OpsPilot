# Governed Execution Plane

M8 keeps the existing structured `ActionRequest`, deterministic `ActionPolicyEngine`, and durable
approval boundary. It adds a transport-neutral execution plane after authorization:

```text
ActionRequest -> Policy -> Approval -> ExecutionRouter -> ExecutionRecord + Outbox
                                                     -> Dispatcher -> Backend
                                                     -> Reconciler -> Verification
```

## Boundaries

`ExecutionBackend` exposes `prepare`, `submit`, `get_status`, and `reconcile`. Mock and Ansible are
adapted to that contract; `HarnessPipelineExecutionBackend` uses the official Harness CD pipeline
HTTP API. Domain, Policy, Workflow, AI, and MCP do not import Harness or its HTTP client.

The caller describes a business action only. Operator-owned `ExecutionProfile` objects contain the
backend, environment, allowed action types, target mapping, immutable pipeline identifier, and an
optional rollback profile. `ExecutionRouter` deterministically maps action type plus environment to
a profile and checks both profile and backend descriptors. An LLM, API client, or MCP client cannot
choose a backend, account, pipeline, input set, or provider URL.

## Transactional dispatch

Queueing writes an `ExecutionRecord` and one `ExecutionOutboxRecord` in the same transaction. A
PostgreSQL dispatcher claims only `PENDING` messages using `FOR UPDATE SKIP LOCKED`, persists the
`DISPATCHING` intent, and then invokes the external backend. The outbox contains a reference, never
credentials or provider payloads.

An expired `CLAIMED` lease is never reclaimed for dispatch. A crash or HTTP timeout after a remote
side effect may mean Harness accepted the request. The execution therefore becomes `UNKNOWN` and
the outbox becomes `INDETERMINATE`; there is no blind retry. Reconciliation attaches a known remote
execution by the OpsPilot correlation ID where possible, otherwise the state becomes
`RECONCILIATION_REQUIRED` for operator intervention.

## State and verification

Canonical state is `PLANNED`, `APPROVED`, `QUEUED`, `DISPATCHING`, `SUBMITTED`, `RUNNING`,
`SUCCEEDED`, `FAILED`, `CANCELLED`, `UNKNOWN`, or `RECONCILIATION_REQUIRED`. Vendor states never
escape the adapter except as a short safe status string.

Backend success means the approved operation completed. It does not prove the incident is fixed.
Health, metrics, and incident verification run separately. Failed verification leaves the Incident
unresolved and emits `EXECUTION_VERIFICATION_FAILED`. A rollback profile produces a new proposal;
rollback still passes Policy and HITL and is never selected automatically by an LLM.

## Harness contract

Harness account, organization, project, base URL, and API key are operator settings. The profile
provides an allowlisted pipeline identifier. Runtime inputs are limited to service, environment,
target reference, incident ID, and execution ID. Arbitrary YAML, expressions, stages, and pipeline
inputs are not accepted. Real SaaS calls are opt-in; CI uses a deterministic fake HTTP contract.

The adapter follows the official generated Harness SDK contracts for
[`POST /pipeline/api/pipeline/execute/{identifier}`](https://github.com/harness/harness-go-sdk/blob/main/harness/nextgen/docs/ExecuteApi.md)
and
[`GET /pipeline/api/pipelines/execution/{planExecutionId}`](https://github.com/harness/harness-go-sdk/blob/main/harness/nextgen/docs/ExecutionDetailsApi.md).

## Telemetry and audit

Safe spans cover `execution.route`, `execution.dispatch`, `cicd.pipeline.run`,
`execution.reconcile`, and `verification.run`. Safe attributes include execution, incident,
workflow, backend, profile, provider reference, status, and latency—never tokens or raw provider
bodies. Audit events mirror routing, queueing, submission, reconciliation, terminal state, unknown
outcomes, and verification failures.

Execution-plane metrics track dispatches, failures, unknown outcomes, reconciliation, duration,
queue age, and especially backend-success/verification-failure mismatches.
