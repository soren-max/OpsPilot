# Durable Human-in-the-Loop Workflow

M4 turns the remediation approval stop into a resumable execution boundary. The workflow creates
an `ApprovalRequest` through `ApprovalService`, LangGraph calls `interrupt()`, and the configured
checkpointer stores continuation state. An authenticated decision resolves the request and resumes
the exact thread with `Command(resume=...)`.

## Three persistence responsibilities

| Store | Responsibility | Not responsible for |
| --- | --- | --- |
| Incident database | Evidence, diagnosis, approval and audit business facts | Graph continuation internals |
| `WorkflowRun` | Graph/version/status metadata and safe reference IDs | Serialized execution state |
| LangGraph PostgreSQL checkpoint | Node continuation state for a `thread_id` | Business truth or authorization |

Production uses `PostgresSaver`; it creates LangGraph-owned checkpoint tables separately from
Alembic-owned business tables. Tests and the no-service offline demo may explicitly use memory,
but this is not a durable deployment mode.

## Approval lifecycle

`PENDING → APPROVED | REJECTED | EXPIRED` is a one-way state machine. A decision records actor ID,
display name, actor type, timestamp and a redacted reason. A unique `(workflow_run_id,
action_fingerprint)` constraint prevents duplicate requests. Resumption validates the approval,
workflow ID and action fingerprint; `resumed_at` and `execution_task_id` make replay idempotent.

Approval does not authorize an otherwise forbidden action. On resume, `ActionService` reruns the
deterministic policy with the validated approval fact. The workflow has no executor reference and
cannot invoke one directly.

## Interrupt and resume

1. Risk assessment identifies a policy-approved action that requires human approval.
2. The approval node asks `ApprovalService` to create an auditable request.
3. `interrupt()` persists continuation state and the `WorkflowRun` becomes `WAITING`.
4. An authenticated operator approves or rejects with a reason.
5. The application resumes the same LangGraph thread. Approval continues to execution; rejection
   follows the failure path without creating an execution task.

There is no polling or database wait loop. API responses expose approval business fields, never
checkpoint blobs, executor details, prompts, raw model output, secrets or hidden reasoning.

## Operational configuration

`OPSPILOT_WORKFLOW_CHECKPOINT_BACKEND=postgres` requires a PostgreSQL `DATABASE_URL`. `auto` selects
PostgreSQL for PostgreSQL deployments and memory for local SQLite development. Durable deployments
must use `postgres`; checkpoint table setup is idempotent at process initialization.
