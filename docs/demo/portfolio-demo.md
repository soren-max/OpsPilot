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
10. **Agent Timeline (30 seconds).** Keep the live indicator visible and show that durable events
    append through Evidence, Memory, Diagnosis, Grounding, Proposal, Policy, Approval, Execution,
    Verification, and the terminal incident state.
11. **Replay (20 seconds).** Select **Replay Frozen Evidence** and point out the `NO SIDE EFFECT`
    label, frozen evidence/history IDs, grounding result, root-cause/action match, and policy result.

Keep MCP protocol, Qdrant internals, and Harness internals out of the mainline; use them for follow-up.

## Optional UNKNOWN/reconciliation proof

Run `make execution-demo` in a second terminal. Its execution tests include the deterministic
remote-accepted/local-response-lost fixture and prove `UNKNOWN -> no blind retry -> reconciliation`
without a duplicate side effect. In the UI, use the shipped synthetic UNKNOWN record to show the
distinct warning copy and reconciliation metadata. This is intentionally a separate proof path;
the canonical local incident demo does not pretend to inject a real Harness network failure.

## Optional trace export

Leave OTLP unset for the default demo. To demonstrate Langfuse, set the documented
`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, and `OTEL_SERVICE_NAME` values before
starting the API and worker, then open the corresponding `incident.run` trace. Only IDs and bounded
metadata are emitted; evidence bodies, prompts, credentials, and authorization headers are not.

## Three presentation levels

- **Level 1 — Recruiter (30 seconds):** Fault → current evidence → grounded AI proposal → human
  approval → verified recovery.
- **Level 2 — Technical interview (five minutes):** Run the complete lifecycle above and emphasize
  authority boundaries, live durable events, replay isolation, and
  `execution success != incident resolved`.
- **Level 3 — Deep dive:** evidence grounding, hybrid historical memory, MCP interoperability,
  PostgreSQL checkpoint, transactional outbox, UNKNOWN/reconciliation, OTel, and bounded SSH
  modernization.
