# 27 — Reconciliation and idempotency

**Why is `UNKNOWN` not `FAILED`?** A timeout may occur after a provider accepted the command.
Retrying could duplicate a deployment or restart.

**How does recovery work?** OpsPilot uses its execution ID as correlation/idempotency key, queries
provider state, attaches a provider execution ID when found, or requests operator reconciliation.
