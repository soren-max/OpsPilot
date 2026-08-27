# Safety Model

M8.5 keeps SSH below the infrastructure boundary. Deployment YAML is strict, versioned and
operator-owned; it contains references rather than credential values. Callers cannot provide a
host, SSH user, inventory, key, script path, command or argv. Fixed-script control uses only
`ansible.builtin.command.argv` values derived from validated allowlists, while systemd control uses
`ansible.builtin.systemd_service`. Missing profiles or credentials fail closed, and preview,
doctor, API, audit and telemetry outputs omit transport secrets.

M8 preserves the authority chain: models cannot select a backend, execution profile, Harness
pipeline, or provider URL. A timeout after external submission is `UNKNOWN`, never an automatic
retry. Backend success cannot resolve an Incident without separate current-state verification, and
rollback is a new governed proposal.

MCP is not authorization. Annotations, remote descriptions, resources, and output are untrusted and
cannot change risk, evidence ownership, approvals, or executor selection. Private context plus
external content plus mutation raises deterministic composition risk; fixed allowlists, scopes,
bounded models, Policy/HITL, and runtime isolation enforce the response.

## Evidence Before Action

An action reason is required, and the M3A/M3B workflow collects observable evidence before
proposing a change. M3A adds bounded typed evidence collection; M3B requires a grounded diagnosis
to reference only real Incident Evidence IDs before any action proposal is accepted.

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

Action, risk, result, verification, and audit event models exist. Approval, Execution, and
Verification events already enter the incident audit trail (M1C/M2); Agent and Tool events may
extend it in future milestones. Secrets and raw model reasoning must never be stored as audit
evidence.

> An LLM is a decision assistant, not an authorization authority.

## Fail-Closed Rules

- unknown action: schema rejection
- malformed or extra parameters: schema rejection
- unknown target: forbidden by policy and adapter allowlists
- medium-risk action without approval: no executor call
- filesystem path supplied by caller: not part of ActionRequest
- arbitrary shell or process-kill request: no representable ActionType
- unknown/cross-environment deployment profile: resolver rejection
- command-injection value in service mapping: configuration rejection
- missing SSH credential secret-file reference: no Ansible dispatch
# Durable approval safety

Approval is a scoped, auditable decision over one workflow and one action fingerprint—not a
boolean capability. It cannot make a forbidden policy result executable. Resume rejects pending or
mismatched approvals, repeated decisions conflict, and repeated resume returns the existing
terminal workflow without executing again. Checkpoints contain continuation references only; raw
prompts, model responses, hidden reasoning and secrets are excluded from workflow state and audit.
