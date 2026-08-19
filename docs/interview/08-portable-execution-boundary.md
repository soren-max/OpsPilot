# Portable Execution Boundary

Status: **Implemented in M1B**

## Why structured actions instead of arbitrary shell?

OpsPilot's strict `ActionRequest` lets Policy authorize the exact object `ActionService` sends to
an adapter. An Agent cannot smuggle command syntax, inventory, playbook paths, or transport
credentials through the API.

## Why deterministic policy before LLM risk review?

Target membership, action class, and approval state are authorization facts. M1A evaluates them
with deterministic rules. A Risk Agent may add advisory context but cannot override a deny.

## Why remove application-level SSH?

The old API owned addresses, usernames, key references, connectivity tests, and remote paths.
M1B makes a Target logical; operator-owned Ansible inventory contains transport details. The
Agent/API cannot read or modify them.

## Why Ansible for bounded remediation?

`AnsibleActionExecutor` maps restart/status/health to reviewed playbooks and passes typed
variables. It supports repeatable recovery and explicit verification without user-supplied args.

## Why not use Ansible for every infrastructure change?

Deployments and configuration need artifact provenance, promotion, rollout gates, durable state,
and rollback. Packing those into remediation would recreate a universal executor.

## Why separate Observe, Remediate, and Change?

Observe is automatic and read-only. Remediate changes runtime state and requires Policy, HITL,
Ansible, and verification. Change alters desired state and belongs to a governed workflow.

## Why Harness later?

Harness may eventually own durable multi-step change. Adding its SDK before OpsPilot's incident,
proposal, policy, and audit contracts would falsely imply a supported production backend.

## Why GitOps for configuration and deployment changes?

GitOps provides reviewable diffs, provenance, approval history, and reconciliation—properties that
fit Change better than imperative incident-worker commands.

## Why should the Risk Agent remain advisory?

A model can notice contextual risk but may be inconsistent or prompt-injected. OpsPilot records
its assessment as evidence; deterministic policy and human approval retain authority.

## Why LangGraph later instead of a giant prompt?

M2 needs durable evidence, hypotheses, tool results, approvals, retries, and resume points. An
explicit state machine can test and checkpoint these transitions; a giant prompt hides state and
weakens idempotency.
