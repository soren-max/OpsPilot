# OpsPilot Interview Guide

Each short answer is a ~30-second headline. The deep answer is a two-minute discussion outline.

## 1. Why can the LLM not execute?

**30 seconds:** Language-model output is probabilistic and consumes untrusted evidence. It produces a
strict typed proposal; deterministic policy, allowlists, identity-bound approval, routing, and the
executor decide whether a side effect is allowed.

**Two minutes:** Explain prompt injection and hallucination, Pydantic schema rejection, evidence-ID
grounding, policy re-assessment after approval, and why neither MCP metadata nor confidence is an
authorization signal. Point to the arbitrary-shell and caller-selected-backend matrix rows.

## 2. Why is Evidence not Knowledge?

**30 seconds:** Evidence is a current, incident-owned observation that may ground a decision.
Knowledge is historical context that may suggest a hypothesis but cannot prove present state.

**Two minutes:** Discuss provenance, time and incident ownership, separate prompt sections and IDs,
the historical injection test, and the need to recollect current health before any remediation.

## 3. Why require HITL?

**30 seconds:** A typed restart is still a real side effect with context the system may not know.
MEDIUM-risk actions therefore stop durably for an accountable human decision.

**Two minutes:** Cover approver identity, reason, audit event, expiry/conflict behavior, deterministic
re-assessment, and why HITL is risk control rather than a UI confirmation dialog.

## 4. Why is a checkpoint not business state?

**30 seconds:** A checkpoint resumes graph control flow; Incident, Approval, Execution, Evidence, and
Audit records express business truth and invariants independently.

**Two minutes:** Describe stable `thread_id`, JSON references rather than ORM objects, replay, schema
migration, and how a DB record can be inspected/reconciled even if graph state is unavailable.

## 5. Why LangGraph?

**30 seconds:** It provides an explicit graph, interrupts/resume, and pluggable durable checkpoints
without becoming the authorization or domain model.

**Two minutes:** Contrast its graph visualization and checkpoint support with the cost of framework
coupling; explain the ports and domain records that keep replacement feasible.

## 6. Why hybrid historical retrieval?

**30 seconds:** Incident text mixes exact operational tokens with paraphrases. Sparse retrieval
preserves exact matches, dense adds semantic similarity, and RRF combines ranks without incomparable
score calibration.

**Two minutes:** Discuss deterministic offline embeddings, dataset limits, Recall/MRR/RC-hit, the
current result where sparse can win, and why v1 makes no universal superiority claim.

## 7. Why is MCP not authorization?

**30 seconds:** MCP describes and transports capabilities. Its client, server, annotations, and tool
output are all outside the trusted policy boundary.

**Two minutes:** Trace an MCP proposal through auth scopes, broker allowlist, incident evidence
ownership, Action schema, policy and approval; mention there is no execute tool.

## 8. Why are tool annotations untrusted?

**30 seconds:** Annotations are provider metadata, not operator policy. Treating “safe” or “read-only”
labels as authority would allow a compromised tool server to escalate itself.

**Two minutes:** Explain canonical application-owned capability definitions, tool output containment,
schema validation, authorization context, and the poisoning test.

## 9. Why must backend selection be deterministic?

**30 seconds:** The backend determines credentials, blast radius, and external side effects. Only an
operator-owned `(action, environment) -> profile` map can select it.

**Two minutes:** Show that Action/MCP/LLM contracts lack backend/pipeline fields, then describe profile
environment/action bounds, immutable pipeline references, and fail-closed missing routes.

## 10. Why not retry an UNKNOWN external side effect?

**30 seconds:** UNKNOWN can mean the remote system accepted the request while the response was lost.
A retry could duplicate the side effect, so OpsPilot reconciles first.

**Two minutes:** Distinguish a known pre-submission failure from `IndeterminateDispatch`, persist
UNKNOWN plus an indeterminate outbox state, recover expired claims, and attach provider results.

## 11. What does the Transactional Outbox solve?

**30 seconds:** It atomically records the intent to dispatch with the Execution record, closing the
gap between a DB commit and an external call.

**Two minutes:** Cover transaction boundaries, SKIP LOCKED claims, leases, uniqueness/idempotency,
dispatcher crash windows, and why outbox alone does not provide exactly-once external effects.

## 12. How does reconciliation avoid duplicate side effects?

**30 seconds:** It queries the provider using the stable local execution identity or provider handle;
it never creates a second dispatch merely because local status is UNKNOWN.

**Two minutes:** Discuss profile-owned correlation inputs, terminal status mapping, new provider
states mapping to UNKNOWN, audit updates, and limitations when a provider cannot search by key.

## 13. Why does backend success not mean the incident is resolved?

**30 seconds:** Backend success proves only that the requested operation completed. Current service
health must independently confirm recovery before Incident becomes RESOLVED.

**Two minutes:** Walk through SUCCEEDED execution with FAILED verification, audit events, failure
handler, stale success hazards, and scenario E in the execution matrix.

## 14. Why retain SSH but remove ServiceSSH?

**30 seconds:** SSH is a transport detail Ansible may use from operator inventory; it is not a domain
service or Agent-facing command API.

**Two minutes:** Explain the strangler adapter, deployment profile, exact service mapping, fixed script
argv, key reference, synthetic legacy Lab, and path toward systemd without restoring raw SSH power.

## 15. What is missing for real production deployment?

**30 seconds:** Enterprise IAM/tenancy, HA/DR, secret management, hardened network policy, provider
SLAs, production traffic evaluation, operational ownership, and deployment-specific runbooks.

**Two minutes:** Separate architecture evidence from operational proof. Discuss load/chaos/security
testing, SLOs, alert quality, approval escalation, data retention, compliance, model governance,
provider reconciliation guarantees, and a staged shadow/canary rollout.

## 16. Why deterministic policy instead of a Risk Agent?

**30 seconds:** Enforceable authorization needs stable, reviewable rules. An LLM risk reviewer could
advise later, but cannot weaken deterministic policy.

**Two minutes:** Cover reproducibility, audit explanations, deny-by-default, rule/version testing, and
how an advisory M10 reviewer could only raise risk or request evidence.

## 17. What did the benchmark reveal rather than market away?

**30 seconds:** The deterministic investigator is reproducible but narrow: its actual root-cause and
insufficient-evidence accuracy on M3B cases are limited. Grounding and unsupported-action controls
remain strong, so v1 reports both capability and boundary.

**Two minutes:** Explain why expected fixture output is not used as predicted output, why real LLM is
`NOT RUN`, why latency is host-specific, and how the limitation informs M10 without entering it now.

