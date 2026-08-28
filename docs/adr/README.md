# Architecture Decision Records

ADRs record stable architectural choices. This index summarizes them without changing their
original content.

| ADR | Title | Status | Summary |
| --- | --- | --- | --- |
| [0001](0001-structured-actions-over-arbitrary-shell.md) | Structured Actions over Arbitrary Shell | Accepted | Typed actions replace model-generated command strings. |
| [0002](0002-deterministic-policy-before-llm-risk-review.md) | Deterministic Policy before LLM Risk Review | Accepted | Code-based authorization runs before any probabilistic risk advice. |
| [0003](0003-ansible-as-infrastructure-execution-adapter.md) | Ansible as Infrastructure Execution Adapter | Accepted | Fixed playbook mappings isolate transport details from the domain. |
| [0004](0004-separate-remediation-from-governed-change.md) | Separate Remediation from Governed Change | Accepted | Bounded recovery and deployment/change require different governance. |
| [0005](0005-separate-domain-state-from-workflow-checkpoint.md) | Separate Domain State from Workflow Checkpoint | Accepted | Business facts and orchestration position have distinct sources of truth. |
| [0006](0006-typed-observability-queries-over-arbitrary-query-language.md) | Typed Observability Queries over Arbitrary Query Languages | Accepted for M3A | Application-owned queries bound observability access and preserve provenance. |
| [0007](0007-llm-reasoning-with-deterministic-authorization.md) | LLM Reasoning with Deterministic Authorization | Accepted | Models reason over evidence; guards, policy, and HITL retain authority. |
| [0008](0008-durable-human-approval-boundary.md) | Durable Human Approval Boundary | Accepted | Approval identity and checkpoint continuation remain auditable and separate. |
| [0009](0009-historical-incident-memory-is-context-not-evidence.md) | Historical Incident Memory Is Context, Not Evidence | Accepted | Retrieved precedent can inform reasoning but cannot prove facts or authorize action. |
| [0010](0010-mcp-is-an-interoperability-boundary-not-an-authorization-boundary.md) | MCP Is an Interoperability Boundary | Accepted | Protocol interoperability cannot bypass typed ports, Policy, or HITL. |
| [0011](0011-execution-routing-is-deterministic-and-operator-owned.md) | Execution Routing Is Deterministic and Operator-Owned | Accepted | Callers cannot select execution backends or profiles. |
| [0012](0012-transactional-outbox-for-external-side-effects.md) | Transactional Outbox for External Side Effects | Accepted | Durable dispatch intent and reconciliation prevent unsafe retries. |
| [0013](0013-ssh-is-an-infrastructure-detail.md) | SSH Is an Infrastructure Detail | Accepted | Ansible owns SSH details below semantic application contracts. |
| [0014](0014-legacy-migration-uses-strangler-adapters.md) | Legacy Migration Uses Strangler Adapters | Accepted | Selected legacy operations migrate without bypassing governance. |
