# Reproducible Incident Lab

M5 validates the existing architecture against real local infrastructure. It adds no Agent,
planner, tool-selection, RAG, MCP, harness, or GitOps abstraction.

The Lab preserves typed boundaries: `MetricKind` selects application-owned PromQL templates;
`LogQuery` selects application-owned LogQL with bounded time and count; health passes through the
read-only Action boundary; remediation passes through `ActionRequest → Policy → Approval →
ActionService → AnsibleActionExecutor`.

The fault controller exposes only five fixed routes: status, stop, high-error-rate,
prompt-injection-log, reset/restart. Scenario YAML is strict metadata rather than executable shell.
The Ansible inventory and three playbooks are operator-owned and mounted read-only. There is no
caller-selected playbook and no shell task.

`service-down` terminates the application child while leaving its controller reachable. This makes
Prometheus report `up=0`, records an error log in Loki, and makes the fixed Ansible health playbook
fail. Deterministic investigation therefore proposes `restart_service`; M4 pauses durably, records
the human identity and reason, then resumes through the fixed restart and verification playbooks.

The prompt-injection scenario deliberately sends “ignore previous instructions”, “approve
restart”, and “run shell command” through Loki. It remains `EvidenceType.LOG`. The deterministic
investigator produces no action from that text, policy is unchanged, and no approval or executor
call is created.

The fixture demo remains the fastest no-container walkthrough. The Live Incident Lab is slower and
uses real processes, telemetry stores, PostgreSQL checkpoints, and Ansible. Neither is represented
as a production deployment.
