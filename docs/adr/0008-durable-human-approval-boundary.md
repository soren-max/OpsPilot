# ADR 0008: Durable human approval is an execution boundary

- Status: Accepted
- Date: 2026-08-20

## Context

Ending a workflow with `WAITING_APPROVAL` loses its continuation after worker restart. A boolean
such as `approved=true` also loses who decided, when, why, for which workflow and for which exact
action.

## Decision

Represent approval as an immutable-identity request with an explicit lifecycle and resolution
metadata. Persist graph continuation with LangGraph's PostgreSQL checkpointer, independently of
Incident facts and `WorkflowRun` metadata. Pause with `interrupt()` and resume the same thread only
after `ApprovalService` validates a terminal decision and its action fingerprint.

Human approval is the boundary at which an already policy-classified proposal may proceed toward
execution. It is not a replacement for policy. `ActionService` reruns policy, and only it can reach
the configured executor.

## Consequences

- Worker restart does not discard a pending continuation.
- Duplicate request, decision, resume and execution attempts are bounded by stable identities.
- Approval history supports audit and incident review.
- Operators must maintain PostgreSQL checkpoint tables in addition to Alembic business tables.
- Full IAM, multi-party/quorum approval and automatic expiry scheduling remain future work.
