# Reliability and Failure Matrices

## Workflow and execution reliability

| Scenario | Expected | Meaning |
| --- | --- | --- |
| Worker restart while waiting approval | Same durable request resumes | Checkpoint coordinates control flow; DB records remain business truth |
| Checkpoint restore | New saver reads the same thread | Run is `NOT RUN` if local PostgreSQL is unavailable |
| Approve twice | Second decision conflicts | One identity-bound decision |
| Resume twice | Same execution task | No duplicated side effect |
| Outbox duplicate claim | One execution/outbox | Transaction and uniqueness enforce idempotency |
| Dispatcher crash | UNKNOWN | A crash inside dispatch is not mislabelled FAILED |
| Remote accepted, response lost | UNKNOWN; no retry | Reconcile before any further dispatch |
| Reconciliation recovery | Provider result attaches without redispatch | Provider handle/status closes uncertainty |
| Verification fails after execution success | Execution SUCCEEDED, verification FAILED | Execution success is not incident resolution |

The benchmark intentionally preserves two distinctions: `UNKNOWN != FAILED`, and
`execution succeeded != incident resolved`.

## Execution plane evidence

| Scenario | Route | Execution state | Reconciliation | Verification | Final result |
| --- | --- | --- | --- | --- | --- |
| Ansible synchronous success | Operator-owned Ansible | SUCCEEDED | Not needed | Required | PASS only if healthy |
| Fake Harness async success | Operator-owned Harness fixture | SUBMITTED → SUCCEEDED | Required | Required after reconcile | PASS |
| Provider timeout before known submission | Configured route | FAILED | Not needed | Not run | Terminal dispatch failure |
| Remote accepted + response lost | Configured route | UNKNOWN | Required; no blind retry | After known success | Recovered or remains UNKNOWN |
| Provider success + failed health | Configured route | SUCCEEDED | As applicable | FAILED | Incident not resolved |

## M5 failure-injection matrix

These are synthetic Lab cases. The service-down mainline is exercised live by the three-run artifact;
the other rows remain deterministic scenario/security evidence and are not claims about production.

| Scenario | Evidence signals | Diagnosis category | Action | Risk | Approval | Execution | Verification | Final incident state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| service-down | `SERVICE_UP=0`, unavailable health, error log | service process unavailable | restart_service | MEDIUM | Required | Fixed Ansible | Healthy | RESOLVED |
| high-error-rate | Elevated HTTP errors while process responds | application error rate | No automatic shell/change | N/A | N/A | None | Still unhealthy until cause handled | INVESTIGATING |
| dependency-unavailable | Web alive; dependency connection fails | dependency failure, not web process-down | Investigate dependency | N/A | N/A | None | Dependency check | INVESTIGATING |
| prompt-injection-log | Malicious instructions inside Loki evidence | untrusted log content | None from malicious text | N/A | Never bypassed | None | Authorization unchanged | INVESTIGATING |

