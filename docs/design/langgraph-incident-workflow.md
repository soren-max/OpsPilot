# LangGraph Incident Workflow

M2 composes the existing Incident and Action application boundaries with a deterministic
LangGraph `StateGraph`:

```mermaid
flowchart TD
  Start --> Load[load_incident]
  Load --> Collect[collect_context]
  Collect --> Investigate[investigate]
  Investigate --> Diagnose[diagnose]
  Diagnose -->|no action| Finalize[finalize]
  Diagnose -->|action| Propose[propose_action]
  Propose --> Risk[assess_risk]
  Risk -->|forbidden| Finalize
  Risk -->|read only| Execute[execute]
  Risk -->|approval required| Pause[WAITING_APPROVAL]
  Execute --> Verify[verify]
  Verify -->|success| Finalize
  Verify -->|failed| Failure[failure]
  Finalize --> End
  Pause --> End
  Failure --> End
```

## State and capabilities

`IncidentWorkflowState` is JSON-serializable and carries IDs, status, structured investigation
fields, action type, risk, verification status, and safe errors. Durable Incident data remains in
SQL tables. Each node receives application capabilities through LangGraph runtime context and
returns a minimal state update; nodes do not query SQLAlchemy or invoke subprocesses directly.

The investigator is deterministic in M2. Service-status evidence containing `unavailable`
proposes a restart, `read-only-check` proposes a status action, and other evidence produces no
action. These rules make routing reproducible without an LLM or hidden reasoning.

## Persistence, replay, and trace

`workflow_runs` records business metadata independently from checkpoints. Idempotency is scoped
by Incident, actor, and client key. Stable graph configuration uses the WorkflowRun ID as
`thread_id`. Hypothesis, diagnosis, proposal, execution reference, finalization, and workflow
audit emission guard against terminal or duplicate replay.

Node start/completion and workflow start/pause/failure/completion events are appended to the
Incident audit timeline with only node, duration, workflow ID, correlation ID, and safe status.
Graph state is never dumped into audit.

M2 retries only `WorkflowInfrastructureFailure` at the execution node. Domain errors, forbidden
policy, approval boundaries, and verification failure are not retried. Medium-risk mutation stops
in `WAITING_APPROVAL`; M4 will add identity-bound durable interrupt/resume.
