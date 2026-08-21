# Reproducible Incident Scenarios

These fixtures explain how OpsPilot turns bounded incident evidence into a grounded diagnosis,
a typed action proposal, a persisted continuation identity, approval, mock execution, and verification. They contain synthetic names and
values only. No API key, database, Prometheus, Loki, ticket system, or network access is used.

Run the default scenario from the repository root:

```bash
make demo
```

Run another fixture:

```bash
uv run --project backend --no-sync python -m app.demo demo/incidents/high-error-rate.yaml
```

Every fixture declares incident metadata, service and environment, symptoms, expected evidence,
diagnosis, action proposal, and final workflow state. The runner independently derives a diagnosis
with transparent deterministic rules, checks it against the expected result, creates a strict
`ActionRequest`, and uses the real deterministic `ActionPolicyEngine` to assess risk. It pauses at
`WAITING_APPROVAL`, records a deterministic offline checkpoint identity, approves, resumes through
the real `ActionService`, invokes only `MockActionExecutor`, verifies, and ends at `SUCCEEDED`.

| Scenario | Demonstrates |
| --- | --- |
| `service-unavailable.yaml` | Complete metric, log, health, and ticket evidence flow |
| `high-error-rate.yaml` | Grounded diagnosis from degraded service signals |
| `prompt-injection-evidence.yaml` | Instruction-like evidence is untrusted and cannot bypass grounding or policy |

The canonical terminal transcript is in
[`expected-results/service-unavailable.txt`](expected-results/service-unavailable.txt).
