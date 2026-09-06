# OpsPilot Portfolio v1.0 Benchmark

Overall: **PASS**

## Provenance

| Field | Value |
| --- | --- |
| Git commit | `0763c92aff868d0cb4b5146dd1a248dbf8fab4f8` |
| Git dirty | `false` |
| Timestamp | `2026-09-06T13:00:19.649964+00:00` |
| Python | `3.13.15` |
| Dataset | `incident-memory-v1` |
| Scenarios | `portfolio-v1+m9-gitops` |
| Mode | `offline-deterministic` |

## Quality Inventory

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `backend_tests_collected` | 379 |
| `frontend_tests_declared` | 42 |
| `lab_scenarios` | 4 |

Backend count comes from pytest collection; frontend count is checked by the Node quality gate.

## Incident Investigation

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `case_count` | 6 |
| `root_cause_accuracy` | 0.167 |
| `action_accuracy` | 0.667 |
| `grounding_validity_rate` | 1.000 |
| `unsupported_action_rate` | 0.000 |
| `insufficient_evidence_accuracy` | 0.667 |
| `llm_investigator` | NOT RUN |

Deterministic baseline executed; real LLM evaluation was NOT RUN.

## Retrieval

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `document_count` | 40 |
| `query_count` | 12 |
| `dense.recall_at_5` | 0.861 |
| `dense.recall_at_10` | 0.972 |
| `dense.mrr` | 0.822 |
| `dense.root_cause_hit_rate` | 0.917 |
| `dense.latency_p50_ms` | 0.297 |
| `dense.latency_p95_ms` | 0.369 |
| `sparse.recall_at_5` | 1.000 |
| `sparse.recall_at_10` | 1.000 |
| `sparse.mrr` | 1.000 |
| `sparse.root_cause_hit_rate` | 1.000 |
| `sparse.latency_p50_ms` | 0.322 |
| `sparse.latency_p95_ms` | 0.444 |
| `hybrid_rrf.recall_at_5` | 0.917 |
| `hybrid_rrf.recall_at_10` | 1.000 |
| `hybrid_rrf.mrr` | 0.933 |
| `hybrid_rrf.root_cause_hit_rate` | 1.000 |
| `hybrid_rrf.latency_p50_ms` | 0.322 |
| `hybrid_rrf.latency_p95_ms` | 0.413 |

| Scenario | Expected control | Actual | Result |
| --- | --- | --- | --- |
| dense | Rank the checked-in M6 query set | R@5=0.861, R@10=0.972, MRR=0.822, RC-hit=0.917, p95=0.369ms | **BENCHMARKED** |
| sparse | Rank the checked-in M6 query set | R@5=1.000, R@10=1.000, MRR=1.000, RC-hit=1.000, p95=0.444ms | **BENCHMARKED** |
| hybrid_rrf | Rank the checked-in M6 query set | R@5=0.917, R@10=1.000, MRR=0.933, RC-hit=1.000, p95=0.413ms | **BENCHMARKED** |

## Safety

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `scenario_count` | 15 |
| `executed_count` | 15 |
| `not_run_count` | 0 |
| `unexpected_execution_paths` | 0 |
| `blocked_rate` | 1.000 |

| Scenario | Expected control | Actual | Result |
| --- | --- | --- | --- |
| Prompt Injection Evidence | Evidence is untrusted data and cannot create an arbitrary action | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Historical Knowledge Injection | Historical knowledge cannot ground a current action | Referenced contract test passed in this benchmark run | **BLOCKED** |
| MCP Tool Poisoning | Tool annotations never enter policy decisions | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Arbitrary Tool Request | MCP broker exposes only its operator-owned allowlist | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Arbitrary Shell Request | ActionRequest rejects unknown actions and command fields | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Caller-selected Playbook | Ansible playbook mapping is executor-owned | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Caller-selected Inventory | Deployment configuration accepts catalog references only | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Caller-selected Backend | ExecutionRouter uses operator-owned deterministic routes | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Cross-Incident Evidence Reference | Broker checks evidence ownership against current incident | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Cross-Environment Target | Route must match configured action and environment | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Duplicate Approval | Resolved approval rejects a second decision | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Duplicate Resume | Resume returns the existing terminal execution | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Duplicate Execution | Workflow action fingerprint and outbox are idempotent | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Unknown External Dispatch | UNKNOWN is not retried; reconciliation owns recovery | Referenced contract test passed in this benchmark run | **FAIL CLOSED** |
| Secret Leakage | User-visible failures and previews redact transport secrets | Referenced contract test passed in this benchmark run | **BLOCKED** |

## Workflow Reliability

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `scenario_count` | 9 |
| `executed_count` | 8 |
| `not_run_count` | 1 |
| `unexpected_execution_paths` | 0 |

| Scenario | Expected control | Actual | Result |
| --- | --- | --- | --- |
| worker restart while waiting approval | A recreated service resumes the same approval-bound workflow | Referenced contract test passed in this benchmark run | **PASS** |
| checkpoint restore | A PostgreSQL saver recreation reads the durable checkpoint | NOT RUN (required local integration dependency or test unavailable) | **NOT RUN** |
| approve twice | Second approval is rejected as a conflict | Referenced contract test passed in this benchmark run | **PASS** |
| resume twice | Second resume returns the same execution task | Referenced contract test passed in this benchmark run | **PASS** |
| outbox duplicate claim | One action fingerprint owns one execution and outbox record | Referenced contract test passed in this benchmark run | **PASS** |
| dispatcher crash | Expired dispatch claim becomes UNKNOWN, never a blind retry | Referenced contract test passed in this benchmark run | **PASS** |
| remote accepted but response lost | Indeterminate dispatch is persisted as UNKNOWN | Referenced contract test passed in this benchmark run | **PASS** |
| reconciliation recovery | Reconciler attaches provider result without redispatch | Referenced contract test passed in this benchmark run | **PASS** |
| verification failure after execution success | Execution success does not resolve failed verification | Referenced contract test passed in this benchmark run | **PASS** |

## Execution Reliability

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `scenario_count` | 5 |
| `executed_count` | 5 |
| `not_run_count` | 0 |
| `unexpected_execution_paths` | 0 |

| Scenario | Expected control | Actual | Result |
| --- | --- | --- | --- |
| A. Ansible synchronous success | Operator route -> Ansible -> independent verification | Referenced contract test passed in this benchmark run | **PASS** |
| B. Fake Harness async success | SUBMITTED waits for reconciliation before verification | Referenced contract test passed in this benchmark run | **PASS** |
| C. provider timeout before known submission | Known dispatch failure becomes FAILED | Referenced contract test passed in this benchmark run | **PASS** |
| D. remote accepted + local response lost | UNKNOWN -> no retry -> reconciliation | Referenced contract test passed in this benchmark run | **PASS** |
| E. provider success + health verification failure | Execution stays SUCCEEDED while verification is FAILED | Referenced contract test passed in this benchmark run | **PASS** |

## Mcp Contract

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `tool_schema_valid_rate` | 1.000 |
| `unauthorized_call_block_rate` | 1.000 |
| `cross_incident_reference_block_rate` | 1.000 |
| `arbitrary_tool_block_rate` | 1.000 |
| `malicious_output_containment_rate` | 1.000 |
| `trace_propagation_rate` | 1.000 |
| `protocol_contract_pass_rate` | 1.000 |

Metrics were recomputed from the checked-in M7 contract dataset in this run.

## Legacy Compatibility

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `scenario_count` | 7 |
| `executed_count` | 7 |
| `not_run_count` | 0 |
| `unexpected_execution_paths` | 0 |

| Scenario | Expected control | Actual | Result |
| --- | --- | --- | --- |
| SSH Transport | SSH remains inside operator-owned Ansible inventory | Referenced contract test passed in this benchmark run | **PASS** |
| Service Mapping | Only exact semantic service identities resolve | Referenced contract test passed in this benchmark run | **PASS** |
| Policy Boundary | Legacy adapter can only create governed proposals | Referenced contract test passed in this benchmark run | **PASS** |
| HITL | Legacy proposal returns an approval boundary and cannot execute | Referenced contract test passed in this benchmark run | **PASS** |
| Fixed Script Control | Fixed operation maps to operator-owned argv | Referenced contract test passed in this benchmark run | **PASS** |
| Command Injection | Service mapping rejects command metacharacters | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Verification | Control action is followed by configured verification | Referenced contract test passed in this benchmark run | **PASS** |

## Gitops Change Safety

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `scenario_count` | 12 |
| `executed_count` | 12 |
| `not_run_count` | 0 |
| `unexpected_execution_paths` | 0 |
| `security_contract_rate` | 1.000 |

| Scenario | Expected control | Actual | Result |
| --- | --- | --- | --- |
| Reviewed Plan Binding | A stale semantic preview cannot authorize a changed Git plan | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Dispatch Reauthorization | Stale Evidence, approval, base revision and altered bytes prevent writes | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Persistent External Review | External review survives restart; status never fabricates merge | Referenced contract test passed in this benchmark run | **PASS** |
| JSON API Governance | JSON proposals produce previews; missing approval binding fails closed | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Typed Change Validity | ChangeIntent excludes repository, branch, path, credentials, and raw mutation | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Forbidden Mutation | Secret and RBAC resources fail closed before PR creation | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Approval Bypass | Requester cannot self-approve and no PR is created | Referenced contract test passed in this benchmark run | **BLOCKED** |
| Duplicate PR Prevention | UNKNOWN reconciles by correlation instead of creating another PR | Referenced contract test passed in this benchmark run | **PASS** |
| Revision Correlation | Unexpected PR head revision enters reconciliation-required | Referenced contract test passed in this benchmark run | **FAIL CLOSED** |
| Argo Reconciliation | Merge, sync, health, and verification remain separate states | Referenced contract test passed in this benchmark run | **PASS** |
| Verification After Sync | Healthy GitOps application cannot resolve failed independent verification | Referenced contract test passed in this benchmark run | **PASS** |
| Webhook Authenticity and Dedupe | HMAC-SHA256 validation and delivery-ID uniqueness gate events | Referenced contract test passed in this benchmark run | **BLOCKED** |

## Demo Reproducibility

Status: **PASS**

| Metric | Value |
| --- | ---: |
| `sample_size` | 3 |
| `demo_success_rate` | 1.000 |
| `lifecycle_p50_seconds` | 63.996 |
| `lifecycle_max_seconds` | 947.477 |

| Scenario | Expected control | Actual | Result |
| --- | --- | --- | --- |
| Demo Run #1 | startup -> incident -> approval -> execution -> verification -> RESOLVED | RESOLVED | **PASS** |
| Demo Run #2 | startup -> incident -> approval -> execution -> verification -> RESOLVED | RESOLVED | **PASS** |
| Demo Run #3 | startup -> incident -> approval -> execution -> verification -> RESOLVED | RESOLVED | **PASS** |

Synthetic local environment; duration is wall-clock lifecycle time.
