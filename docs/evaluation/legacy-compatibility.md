# Synthetic Legacy Compatibility Report

Scope: the checked-in `legacy-host` Docker target only. This is **not a company or production
environment**. `make legacy-demo` exercises Ansible → SSH transport → operator-owned fixed script →
service restart → current verification. `make portfolio-benchmark` re-executes the bounded contract
tests behind this report.

| Compatibility control | Expected result |
| --- | --- |
| SSH Transport | PASS |
| Service Mapping | PASS |
| Policy Boundary | PASS |
| HITL | PASS |
| Fixed Script Control | PASS |
| Command Injection | BLOCKED |
| Verification | PASS |

The generated `artifacts/legacy-compatibility.json` combines the live lifecycle transcript with the
deployment/architecture contract suite. It does not infer the seven results from exit code alone.

Private keys are runtime references, not request fields. The Agent, LLM, MCP client, and legacy API
cannot select SSH host/user, inventory, playbook, script path, command, or argv.
