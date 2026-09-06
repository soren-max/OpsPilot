# Deterministic Change Policy

Every `CHANGE` is at least `HIGH` risk and requires explicit OpsPilot approval. An LLM may propose a
typed intent, but cannot assign risk, authorize a PR, select infrastructure coordinates, or override
a deny.

The policy evaluates both the intent and the planned semantic `ChangeSet`:

| Check | Fail-closed result |
| --- | --- |
| Service and environment match profile and Incident | `FORBIDDEN` |
| Change type and resource are allowlisted | `FORBIDDEN` |
| Current incident-local Evidence exists | `FORBIDDEN` |
| Changed field is allowlisted | `FORBIDDEN` |
| Image is an allowlisted-registry SHA-256 digest | `FORBIDDEN` |
| Replica count is within the operator ceiling | `FORBIDDEN` |
| Explicit OpsPilot approval exists | Otherwise not allowed |

The manifest validator denies Secret, ServiceAccount, RBAC binding/cluster role, admission webhook,
CRD, Namespace, hostPath, host networking/PID, privileged and privilege-escalating workloads. The
bounded planner never accepts arbitrary YAML, JSON Patch, commands/args, or environment secret
material from an agent.

Gate A (OpsPilot approval) authorizes only creation of the reviewed PR. Gate B (Git review) controls
entry into the protected base branch. The two records and UI states must never be conflated.
