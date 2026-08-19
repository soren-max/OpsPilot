# ADR 0004: Separate remediation from governed change

Status: Accepted

## Context

OpsPilot previously placed status, service scripts, remote commands, and deployment-like
operations behind one executor abstraction. Transport configuration and broad command authority
therefore appeared to be application features.

## Decision

OpsPilot separates Observe, Remediate, and Change. M1B only implements bounded remediation through
strict actions, deterministic policy, approval, Ansible, and verification. Deploy, rollback,
configuration, and IaC remain planned governed workflows.

## Rationale

A restart uses an existing deployment, a small parameter surface, and immediate status
verification. A deploy selects an artifact, rollout strategy, promotion, health gates, and
rollback. Treating both alike would under-govern deploys or overcomplicate incident recovery.

Ansible fits a small restart/reload/status catalog because every `ActionType` maps to an
application-owned playbook and only validated variables cross the port. Operator inventory owns
infrastructure details.

Complex change needs durable multi-step state, artifact provenance, approvals, rollout gates,
cancellation, and rollback. A future Harness integration may own those mechanics while OpsPilot
supplies investigation, proposal, and risk context. GitOps is preferable for declarative changes
because review and reconciliation live in version control.

A universal executor would accumulate shell, transport, deployment, and workflow parameters until
the port became an authorization bypass. Narrow ports keep authority explicit.

## Consequences

Each remediation action requires schema, policy, playbook mapping, verification, and tests. Change
features wait for a governed workflow rather than reusing remediation infrastructure.
