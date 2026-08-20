# Architecture

## Operating model

OpsPilot separates three lifecycles with different authority and failure semantics.

M1C adds the durable incident path around those execution lifecycles:

```text
Alert / User
     |
     v
  Incident -> Evidence -> Hypothesis -> Diagnosis -> Action Proposal
                                                   |
                                                   v
                 Knowledge Projection <- Resolve <- Verification
                                                   ^
                                                   |
                            Policy -> Approval -> Execution
```

Incident, Evidence, Hypothesis, Diagnosis, append-only AuditEvent, timeline, optimistic locking,
and the resolved-incident knowledge projection are implemented in M1C. M2 adds LangGraph
orchestration over those application capabilities. LLM reasoning, runtime retrieval/RAG, and
multi-agent behavior remain planned.

```text
Observe                         Remediate                         Change
   |                                |                                |
   v                                v                                v
Read-only capabilities       Structured Action              Governed Workflow
metrics / logs / ticket      -> deterministic Policy        -> Harness / GitOps
status / health              -> human approval              (planned)
                              -> Ansible
                              -> verification
```

Observation is automatic and read-only. Metrics, logs, tickets, status, and health return
evidence without mutation authority.

Remediation is bounded recovery such as restart or reload. The API constructs a strict
`ActionRequest`; `ActionPolicyEngine` authorizes it, HITL approves state changes, `ActionService`
orchestrates preview/execute/verify, and an injected Mock or Ansible adapter runs only an
application-owned mapping.

Change includes deploy, rollback, configuration, and IaC. These require rollout, promotion, and
rollback lifecycles, so they remain outside remediation. A future governed backend may integrate
Harness and GitOps; neither is implemented in M1B.

## Portable boundary

- `app/domain` has no transport or infrastructure credential concepts.
- `app/application` depends only on the `ActionExecutor` port.
- API clients cannot select executor, inventory, playbook, process, shell, or argument vector.
- Logical Targets contain identity, environment, description, enabled state, labels, and service
  deployments. Connection data belongs to operator-owned Ansible inventory.
- Playbook mapping is application code; dependency injection selects Mock or Ansible.
- Worker bootstrap is the composition root: each polling iteration derives the enabled Target
  allowlist, constructs one operator-selected Mock or Ansible `ActionService`, and shares it
  between `WorkflowService` and `WorkerService`.
- Workflow runtime never imports or implicitly selects an executor implementation. A workflow
  that reaches policy or execution without an injected `ActionService` fails closed as an
  infrastructure configuration failure.

Ansible may internally use SSH according to operator-owned inventory. That is an implementation
detail, not part of the OpsPilot application, Agent, API, or ActionRequest contract.

## Explicit state, not hidden reasoning

The M2 workflow stores identifiers, status, decision summaries, proposed action types, and risk
results. It does not put ORM objects, sessions, executors, raw logs, or hidden chain-of-thought in
checkpoint state. Nodes call application capabilities and return minimal serializable updates.

Incident status is stable business state, not a future LangGraph node name. Every state change
passes through the explicit lifecycle table and a version compare-and-set. Its AuditEvent is
inserted in the same transaction. Incident/action association lives in the application layer, so
the reusable Action domain contains no Incident ORM or foreign key.

The Incident database is the domain source of truth. LangGraph checkpoints only record execution
position and workflow-local references. `WorkflowRun` is durable OpsPilot metadata and uses a
stable graph thread identifier equal to its workflow ID. M2's in-memory checkpointer is limited to
development and tests. `WorkflowService` accepts LangGraph's existing `BaseCheckpointSaver`
directly instead of wrapping it in a second application-specific checkpoint port. Durable
Postgres checkpoint and approval resume remain deferred to M4.
