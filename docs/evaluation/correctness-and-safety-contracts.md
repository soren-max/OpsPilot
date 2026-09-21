# Correctness and Safety Contracts

This document records the correctness and security invariants the PR
`fix: harden incident correctness and execution safety contracts` established, what regression
test proves each one, and where the boundary of the claim is. It is deliberately narrow: these are
the behaviours OpsPilot actually verifies, not a claim of comprehensive correctness or security.

## Invariants

| # | Invariant | Verdict | Regression evidence |
| --- | --- | --- | --- |
| 1 | Critical metric values selected for investigation reach the Investigator context | PASS | `tests/ai/test_investigator_context_fidelity.py` |
| 2 | Insufficient evidence cannot silently resolve an incident | PASS | `tests/workflows/test_incident_finalization.py` |
| 3 | Workflow completion is not equivalent to incident resolution | PASS | `tests/workflows/test_incident_finalization.py` |
| 4 | REMEDIATE approval is bound to execution-relevant request content | PASS | `tests/test_remediate_approval_binding.py` |
| 5 | Modified approved requests require re-approval | PASS | `tests/test_remediate_approval_binding.py` |
| 6 | Model/frontend input cannot enlarge actor or execution capability | PASS | `tests/test_remediate_approval_binding.py`, `tests/architecture/test_ai_architecture.py` |
| 7 | Known secrets are sanitized before model-, replay-, API- and telemetry-visible boundaries | PASS (bounded) | `tests/test_sensitive_data_boundary.py` |
| 8 | A reconciled successful execution resumes from execution state instead of re-approving | PASS | `tests/execution/test_async_resume.py` |
| 9 | UNKNOWN external side effects are never blindly retried | PASS | `tests/execution/test_failure_classification.py` |
| 10 | Replay operates on the original frozen Investigator input and has no execution side effects | PASS | `tests/test_replay_input_fidelity.py` |

## What each invariant means in the code

**1. Investigator context fidelity.** `EvidenceContextBuilder` packs bounded, typed, deterministic
evidence. Allowlisted metadata keys keep scalars and bounded scalar lists (so a Prometheus
`selected_values: [0]` reaches the model instead of degrading to `series_count: 1`), nested
structures are dropped, current evidence is budgeted before historical context, and truncation is
recorded per item (`truncated`) rather than silently applied. No summarizer runs, so `summarized`
is always `false`. The prompt version is a single constant shared by the prompt and the
Investigator metadata.

**2 and 3. Finalization semantics.** Resolution requires an independently verified remediation:
`successful = action_needed AND not policy_blocked AND verification_status == SUCCEEDED`. Proposing
no action, lacking evidence, failing policy, or failing verification never resolves an incident. An
inconclusive run completes the workflow (`SUCCEEDED`) while the incident stays `INVESTIGATING`, so
workflow completion and incident resolution are different facts. No new incident status was added.

**4, 5 and 6. Approval binding.** `app/execution/binding.py` derives a canonical digest over the
execution-relevant request content (action type, target, environment, parameters) plus the resolved
execution backend, profile identity, and profile configuration. Explanation prose is deliberately
excluded, and the digest is independent of JSON key ordering. Dispatch recomputes the digest and
blocks with an `APPROVAL_STALE` audit event when it differs, before any external call. Unknown
environments fail closed instead of defaulting to `development`. The approval actor is always the
server-side authenticated user; the model output and the approval request body have no actor, role,
profile, or backend field.

**7. Sensitive data boundary.** One sanitizer redacts an enumerated set of credential shapes
(Authorization headers, JWTs, `api_key`/`token`/`secret`/`password` assignments including quoted
JSON forms, database DSNs, PEM private-key blocks, cloud access keys, webhook secrets, and URL
userinfo) at Evidence ingestion, in the log formatter, and in span exception recording. Redaction is
keyed on known shapes plus key names, never on entropy alone, so UUIDs, content hashes, trace IDs,
hostnames, and timestamps survive unchanged.

**8. Async execution resume.** `WorkflowService.resume_execution` consumes the durable execution
result and re-enters the graph *after* the execute node, so a reconciled success flows to
verification and finalization. It never re-proposes the action, re-requests the approval, or
dispatches twice. An execution still in flight leaves the workflow `WAITING`.

**9. Failure classification.** The Harness client separates connect-phase failures (provably not
submitted → bounded retry is safe) from post-submission failures — read/write errors, resets,
timeouts, ambiguous 5xx, and missing acceptance handles — which become `UNKNOWN` and are never
retried. The durable outbox message moves to `INDETERMINATE`, not back to `PENDING`. The ordinary
worker retries only read-only checks, because a failed write does not prove the remote side effect
did not happen.

**10. Replay fidelity.** The frozen snapshot stores the evidence that actually entered the
Investigator (identifiers *and* sanitized content), the historical-knowledge snapshot, the prompt
version, the context-builder configuration, and the model metadata. Replay reconstructs from that
snapshot rather than re-deriving a similar-looking selection, so later evidence or changed memory
cannot alter a frozen replay.

## Explicit boundaries

These contracts are bounded in the following ways. They are not hidden caveats; they are the
current limits of the claim.

- **Redaction is not DLP.** Only enumerated credential shapes and sensitive key names are removed.
  An unrecognized secret format that matches none of the patterns, and that is not carried under a
  sensitive key name, is not detected. There is no content-classification service, no per-tenant
  policy, and no entropy-only fallback.
- **No exactly-once side effects.** Delivery remains explicitly at-most-once-per-dispatch with an
  `UNKNOWN` state. When a provider exposes no remote execution handle, no correlation API, and no
  idempotency key, OpsPilot cannot rediscover the outcome and requires manual reconciliation. It
  does not pretend otherwise.
- **Reconciliation is not automatic for every provider.** Automatic resume covers a terminal
  reconciled result. An execution in `RECONCILIATION_REQUIRED` still needs an operator.
- **Fail-closed environments are a gate, not a migration.** An incident whose environment string is
  not in the alias table (`development`/`dev`/`local`/`lab`, `test`/`testing`/`test-mock`,
  `production`/`prod`) cannot start a remediation workflow. Existing incidents with other
  environment strings will fail closed until the alias table is extended.
- **Approval binding is not IAM.** The actor identity model is unchanged: it trusts the existing
  authenticated server-side session. This work verifies that model and frontend input cannot widen
  actor, role, profile, or capability; it does not add roles, tenancy, or delegation.
- **The LLM Investigator path is not exercised in the default artifact.** `llm_investigator` remains
  `NOT RUN`; the deterministic fixtures are what the generated benchmark measures.
- **Frozen replay covers completed investigations.** A workflow whose investigation failed keeps the
  pre-investigation snapshot, which is broader than the input a failed run would have used.
- **The PostgreSQL resume test is skip-guarded.** It runs in the CI job that provisions PostgreSQL
  and sets `OPSPILOT_TEST_POSTGRES_URL`, with the psycopg-3 dialect normalized explicitly. It is
  skipped where no database is configured.