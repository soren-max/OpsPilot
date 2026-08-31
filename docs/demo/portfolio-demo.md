# Canonical 3–5 Minute Portfolio Demo

## Before the interview

Run `make demo-doctor`, then `make demo-local`. Keep the architecture and incident timeline visible.
State up front that this is a synthetic local Lab, not a production environment.

## Five-minute path

1. **Architecture (30 seconds).** Point to Observability → Evidence → Investigator → Policy → HITL
   → durable Workflow → governed Execution → Verification. The model proposes; it never authorizes.
2. **Inject service-down (20 seconds).** Show `[2/10] Fault injected — service-down`.
3. **Evidence (30 seconds).** Show current Prometheus, Loki, health, and ticket evidence with IDs.
4. **Diagnosis (30 seconds).** Show “Service process unavailable” and its evidence references.
5. **Policy (20 seconds).** Show typed `restart_service`, MEDIUM risk, and the target allowlist.
6. **Approval (30 seconds).** Show the durable approval identity and `WAITING_APPROVAL`.
7. **Resume (20 seconds).** Approve once and show the same workflow resuming from its checkpoint.
8. **Execution (30 seconds).** Show the fixed Ansible playbook; no model/user command enters argv.
9. **Verification (30 seconds).** Show current health independently returning healthy.
10. **Timeline (30 seconds).** End at `Final State: RESOLVED` with audit events.

Keep MCP protocol, Qdrant internals, and Harness internals out of the mainline; use them for follow-up.

## Three presentation levels

- **Level 1 — Recruiter (30 seconds):** Fault → current evidence → grounded AI proposal → human
  approval → verified recovery.
- **Level 2 — Technical interview (five minutes):** Run the complete lifecycle above and emphasize
  authority boundaries plus `execution success != incident resolved`.
- **Level 3 — Deep dive:** evidence grounding, hybrid historical memory, MCP interoperability,
  PostgreSQL checkpoint, transactional outbox, UNKNOWN/reconciliation, OTel, and bounded SSH
  modernization.

