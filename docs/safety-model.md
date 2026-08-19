# Safety Model

## Evidence Before Action

An action reason is required, but a future workflow must also collect observable evidence before
proposing a change. Milestone 1A creates the typed boundary; evidence enforcement is planned.

## Least Privilege

Only enumerated actions with action-specific parameter schemas are accepted. Unknown and extra
fields fail validation. The Ansible adapter owns its inventory, playbook root, action mapping,
and target allowlist. There is no arbitrary shell action.

## Human Control

Read-only actions may proceed automatically. Restarting a service is medium risk and the policy
returns `approval_required=true`; `ActionService` will not invoke an executor without approval.
Durable, identity-bound approval integration is partial and will be completed with workflow
checkpointing.

## Auditable by Design

Action, risk, result, verification, and minimal audit event models exist. Future Agent, Tool,
Approval, Execution, and Verification events will enter an incident audit trail. Secrets and raw
model reasoning must never be stored as audit evidence.

> An LLM is a decision assistant, not an authorization authority.

## Fail-Closed Rules

- unknown action: schema rejection
- malformed or extra parameters: schema rejection
- unknown target: forbidden by policy and adapter allowlists
- medium-risk action without approval: no executor call
- filesystem path supplied by caller: not part of ActionRequest
- arbitrary shell or process-kill request: no representable ActionType
