# Git Side-effect Reconciliation

PR creation is an external side effect. A database transaction first persists the approved,
validated `ChangeRecord` and one `ChangeOutboxRecord`. A leased dispatcher then creates the fixed
`opspilot/change/<change-id>` branch, correlated commit, and PR.

Commit trailers contain only `OpsPilot-Change-ID`, `Incident-ID`, and `Workflow-ID`. The PR body is
generated from safe domain fields and contains Evidence references, semantic diff, risk, approval
reference, verification plan, and Git-native revert guidance. Credentials, raw model output, prompts,
hidden reasoning, and raw provider payloads are excluded.

If the provider may have accepted PR creation before a timeout, the record becomes `UNKNOWN` and the
outbox becomes `INDETERMINATE`. There is no automatic retry. Reconciliation searches by deterministic
branch and Change-ID marker:

- exactly correlated PR found: attach it and continue at `WAITING_REVIEW`;
- outcome cannot be proven: enter `RECONCILIATION_REQUIRED`;
- observed PR head differs from the recorded commit: fail closed;
- Argo reports Synced at a different merged revision: fail closed.

Webhook ingestion verifies `X-Hub-Signature-256` with HMAC-SHA256 over the original body using a
constant-time comparison. It bounds payload size, allowlists event/repository, validates branch
correlation, and deduplicates `X-GitHub-Delivery`, following GitHub's
[delivery validation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
and [event header](https://docs.github.com/en/webhooks/webhook-events-and-payloads) contracts.
Polling remains functional without webhooks.
