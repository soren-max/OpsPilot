# OpsPilot

[English](README.md) | [简体中文](README.zh-CN.md)

**Evidence-grounded, human-controlled incident response.** OpsPilot turns a synthetic alert into
current evidence, a grounded diagnosis and typed action, deterministic policy, durable approval,
governed Ansible/Harness execution, independent verification, and an auditable result. A model may
propose; it cannot authorize or select the execution path.

**Current Stable Portfolio Release: v1.0 architecture (M1–M8.5).** M9+ is explicit future work.

## Quick Demo

```bash
make demo-local
```

The canonical `service-down` demo is a disposable local environment—not a production claim. It
needs no OpenAI key, Harness SaaS, remote MCP server, or company network and uses Prometheus, Loki,
PostgreSQL checkpointing, Policy/HITL, fixed Ansible remediation, and current health verification.
Use the [3–5 minute interview walkthrough](docs/demo/portfolio-demo.md) or the
[10-minute mentor walkthrough](docs/demo/mentor-demo.md).

## Architecture Freeze

```mermaid
flowchart TD
  Obs[Observability / Alert] --> Evidence[Current Evidence]
  Evidence --> Investigator
  Memory[Historical Memory] --> Investigator
  Investigator --> Action[Structured Action Proposal]
  Action --> Policy[Deterministic Policy]
  Policy --> HITL[Human Approval]
  HITL --> Workflow[Durable Workflow Resume]
  Workflow --> Plane[Governed Execution Plane]
  Plane --> Ansible
  Plane --> Harness
  Ansible --> Verify[Independent Verification]
  Harness --> Verify
  MCP[MCP Interoperability] -. typed proposals / evidence .-> Evidence
  Data[(PostgreSQL / Audit / OpenTelemetry)] --- Workflow
  Data --- Plane
```

The frozen chain is **Alert/Fault → Incident → Evidence → Historical Memory → Investigator →
Structured Action → Policy → HITL → Resume → Governed Execution → Verification → Audit/Telemetry**.
No GitOps, Kubernetes, new Agent framework/vector database/LLM provider/execution backend, or new MCP
feature is introduced by the v1.0 closeout.

## Verifiable Portfolio Evidence

<!-- portfolio-metric backend_tests=320 -->
<!-- portfolio-metric frontend_tests=28 -->
<!-- portfolio-metric lab_scenarios=4 -->
<!-- portfolio-metric investigation_cases=6 -->
<!-- portfolio-metric retrieval_queries=12 -->
<!-- portfolio-metric safety_scenarios=15 -->
<!-- portfolio-metric safety_blocked_rate=1.000 -->
<!-- portfolio-metric mcp_contract_rate=1.000 -->
<!-- portfolio-metric demo_sample_size=3 -->
<!-- portfolio-metric demo_success_rate=1.000 -->

| Evidence | Result | Trace |
| --- | --- | --- |
| Backend / frontend tests | 320 collected / 28 declared | Generated benchmark + quality gate |
| Incident investigation | 6 real deterministic fixtures; LLM `NOT RUN` | [Benchmark entry](docs/evaluation/portfolio-benchmark.md) |
| Hybrid retrieval | 40 documents / 12 queries; Dense, Sparse, Hybrid RRF | [Retrieval evaluation](docs/evaluation/retrieval-benchmark.md) |
| Safety containment | 15/15 controls, 0 unexpected execution paths | [Safety matrix](docs/evaluation/safety-matrix.md) |
| MCP contract | 7/7 metrics recomputed at 1.000 | Generated artifact |
| Reproducible Lab | 4 failure scenarios; service-down demo 3/3 RESOLVED | Generated artifact |
| Ansible over SSH | Synthetic fixed-script lifecycle covered | [Migration guide](docs/migration/legacy-environment-guide.md) |

Run `make portfolio-benchmark` to regenerate JSON and Markdown under `artifacts/`, then
`make portfolio-check` for the release gate. README metric comments are verified by
`scripts/check-portfolio-metrics.py`; host-sensitive latency remains only in the artifact.

## External Execution Failure Handling

```mermaid
flowchart TD
  Tx[DB Transaction] --> Record[ExecutionRecord]
  Tx --> Outbox[Outbox]
  Outbox --> Dispatcher
  Dispatcher --> Backend[External Backend]
  Backend --> Unknown{UNKNOWN?}
  Unknown -- Yes --> NoRetry[NO BLIND RETRY]
  NoRetry --> Reconciler
  Unknown -- No / terminal success --> Verification
  Reconciler --> Verification
  Verification --> Result[Incident result]
```

`UNKNOWN != FAILED`, and `execution SUCCEEDED != incident RESOLVED`. See the
[trade-offs](docs/portfolio/tradeoffs.md), [interview guide](docs/portfolio/interview-guide.md),
[resume pack](docs/portfolio/resume.md), and [explicit limitations](docs/evaluation/limitations.md).

M8.5 adds strict deployment profiles, systemd and fixed-script service control, a read-only doctor,
migration readiness assessment, a safe legacy API/ticket boundary, and a synthetic
Ansible-over-SSH lab. Run `make deployment-preview PROFILE=example-legacy-test`,
`make migration-assess PROFILE=example-legacy-test`, or `make legacy-demo`.

## Demo Profiles

| Capability | Demo Minimal | Demo Full | Production integration |
| --- | --- | --- | --- |
| Prometheus / Loki / Health / Mock Ticket | Included | Included | Configure typed adapters |
| Deterministic investigator | Included | Included | Supported |
| OpenAI investigator | Off | Optional | Operator configuration required |
| Durable HITL / PostgreSQL checkpoint | Included | Included | Auth and deployment configuration required |
| Fixed Ansible remediation | Included | Included | Operator-owned inventory required |
| Historical memory / local Qdrant | Off | Included | Production embedding/vector configuration required |
| MCP capability plane | Off | Included | Auth, trust, and transport configuration required |

The public repository is an independent personal R&D project. The local demo is a disposable Docker
environment, not a claim of production deployment. Real environments require explicit adapters,
credentials, access controls, and operator configuration.

## Why OpsPilot

General-purpose agents can produce plausible commands without operational context or
authorization. OpsPilot separates **assistance from authority**:

- A model may **propose** a typed action, but deterministic policy, target allowlists,
  approval, and an executor boundary decide whether anything can **run**.
- The LLM is a decision assistant, not an authorization authority. Its output is validated,
  grounded, and gated by deterministic controls.
- Every decision path — evidence, diagnosis, proposal, approval, execution, verification — is
  explicit, auditable, and testable.

## Core Principles

- **Evidence Before Action** — investigate before proposing a change.
- **Least Privilege** — expose narrow, typed capabilities, never an arbitrary shell.
- **Human Control** — state-changing actions require explicit approval.
- **Auditable by Design** — decisions, approvals, execution, and verification have durable
  domain boundaries.
- **Deterministic Baseline** — an offline investigator keeps the system reproducible and
  CI-friendly; an LLM is an explicit operator-chosen enhancement, not a hidden dependency.

## Architecture

```mermaid
flowchart TD
  Alert[Alert / User] --> Workflow[LangGraph Incident Workflow<br/>Implemented]
  Workflow --> Caps[Typed Capability Ports<br/>Implemented]
  Caps --> Prom[Prometheus]
  Caps --> Loki[Loki]
  Caps --> Tick[Tickets]
  Caps --> Health[Service Health]
  Prom --> Evidence[(Durable Evidence<br/>M1C)]
  Loki --> Evidence
  Tick --> Evidence
  Health --> Evidence
  Evidence --> Investigator[LLM Investigator<br/>M3B - Implemented]
  Investigator --> Guard[Grounding Guard<br/>Structured Output + Evidence ID validation]
  Guard --> Action[Structured Action Proposal]
  Action --> Policy[Deterministic Policy Engine<br/>Implemented]
  Policy --> Approval{Durable Human Approval<br/>Implemented in M4}
  Approval --> Executor[ActionExecutor<br/>Implemented]
  Executor --> Mock[Mock Adapter<br/>Implemented]
  Executor --> Ansible[Ansible Adapter<br/>Implemented]
  Ansible --> Infra[Target Infrastructure]
  subgraph Advanced[Implemented optional capabilities]
    direction LR
    Postgres[(Postgres Checkpoint<br/>Implemented)]
    HITL[Durable HITL Resume<br/>Implemented]
    Harness[Harness Backend<br/>Implemented in M8]
    RAG[Historical Incident Memory<br/>Implemented in M6]
  end
  Approval -.-> Postgres
  Postgres -.-> HITL
  Executor -.-> Harness
  Investigator -.-> RAG
```

The Action Safety Core is:

```text
ActionRequest -> ActionPolicyEngine -> approval boundary -> ActionExecutor -> verification
```

No model output is passed to a shell, SSH client, inventory path, or playbook path.

## Current Capabilities

**Implemented:**

- LangGraph incident workflow with explicit, JSON-serializable state (`M2`, `M2.1`)
- Typed, bounded Prometheus / Loki capability adapters plus Ticket / Service Health ports (`M3A`)
- Durable Incident, Evidence, and append-only AuditEvent domain (`M1C`)
- Evidence grounding with validated Evidence IDs and bounded context (`M3B`)
- OpenAI structured investigator behind a provider-neutral port (`M3B`)
- Deterministic offline investigator baseline (no API key required)
- Deterministic policy engine with target allowlists and fail-closed rules
- Mock and fixed-mapping Ansible executors behind a dependency-injected port (`M1A`/`M1B`)
- Governed Mock, Ansible, and allowlisted Harness execution profiles with reconciliation (`M8`)
- Audit / evaluation foundation: evaluation fixtures, safety cases, secret scan in CI

**Future work (outside stable v1.0):**

- GitOps governed change workflow (`M9`)
- Advanced evaluation and agent observability (`M10`/`M11`)

## Safety Model

The LLM is a decision assistant, not an authorization authority. Read-only actions can be
allowed automatically. Service restarts are medium risk and remain blocked until approval.
Unknown actions, unknown targets, malformed parameters, and extra fields fail closed.

### Safety Highlights

- **No arbitrary shell** — only enumerated structured actions with strict schemas.
- **No arbitrary PromQL / LogQL** — query templates are application-owned.
- **Evidence IDs validated** — the model can only reference Evidence that exists in the current
  Incident; it cannot invent IDs.
- **Prompt-injected logs/tickets treated as untrusted data** — evidence is serialized as data,
  and enforceable guards (schema, grounding, policy) follow generation.
- **LLM cannot authorize execution** — policy and approval are deterministic.
- **Mutating actions require approval** — medium-risk actions stop at `WAITING_APPROVAL`.
- **Executor selected by operator configuration** — workflow code never selects a backend and
  fails closed if the dependency is absent.
- **No hidden chain-of-thought persistence** — only auditable conclusions are stored.
- **Secret-safe audit metadata** — no credentials, raw prompts, or raw evidence bodies in audit.

See [Safety Model](docs/safety-model.md).

## Demo

Run a complete deterministic walkthrough without an API key, database, Prometheus, Loki, ticket
system, or network access:

```bash
uv sync --project backend --extra dev --locked
make demo
```

The input is `service unavailable`, with `SERVICE_UP = 0`, an error log, unavailable health, and
a related ticket. The terminal result is:

```text
Incident Created
Evidence Collected
  - Metric [ev-service-up] SERVICE_UP = 0
  - Log [ev-error-log] ERROR worker stopped accepting requests
  - Health [ev-health] Health check is unavailable
  - Ticket [ev-ticket] Related ticket reports a failed service start
Investigation Result
Diagnosis
  root_cause=checkout-api is stopped after a failed service start
  evidence_references=ev-service-up, ev-error-log, ev-health, ev-ticket
Action Proposal
  action=restart_service
Risk Assessment
  risk=MEDIUM
WAITING_APPROVAL
```

The checked-in synthetic [incident scenarios](demo/README.md) validate grounded evidence
references and pass the typed proposal through the real deterministic policy engine. The runner
never invokes an executor and stops at `WAITING_APPROVAL`; durable approval and resume belong to
**M4**. See the [recording guide](docs/demo.md) for terminal and architecture walkthroughs.

## Project Tour

Read [Architecture](docs/architecture.md) → [Safety Model](docs/safety-model.md) →
[Incident Workflow](docs/design/langgraph-incident-workflow.md) →
[Observability Capabilities](docs/design/observability-capabilities.md) →
[LLM Investigator](docs/design/llm-investigator.md) → [Roadmap](docs/roadmap.md).

The [documentation index](docs/README.md), [ADR index](docs/adr/README.md), and
[interview preparation index](docs/interview/README.md) provide deeper navigation.

## Quick Start

Two modes are supported; **offline mode needs no paid API key**.

### Offline / deterministic mode (default)

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/), and Node.js 22+.

```bash
uv sync --project backend --extra dev
uv run --project backend pytest backend/tests

cd frontend
npm ci
npm test
npm run dev
```

The default `LLM_MODE=deterministic` (see `.env.example`) runs the fully offline baseline:
no `OPENAI_API_KEY` is required, no network call is made, and CI stays deterministic.

### LLM mode (optional)

Set these in `.env` (never commit `.env`):

```bash
LLM_MODE=llm
LLM_PROVIDER=openai
LLM_MODEL=<model name, e.g. gpt-5-mini>
LLM_API_KEY=<your key>
```

LLM mode requires a valid `OPENAI_API_KEY` and an operator-approved model configuration.
Provider failures are explicit and auditable — there is no silent fallback to the
deterministic baseline.

Copy `.env.example` to `.env` and replace every placeholder before starting the API.

## Current Status

| Area | Status |
| --- | --- |
| M1A Action Safety Core | **Implemented** |
| M1B Portable Execution Boundary | **Implemented** |
| M1C Incident Domain + Audit | **Implemented** |
| M2 LangGraph Incident Workflow | **Implemented** |
| M2.1 Workflow Runtime Hardening | **Implemented** |
| M3A Observability Capabilities | **Implemented** |
| M3B Evidence-Grounded LLM Investigator | **Implemented** |
| M3.5 Portfolio & Demo Readiness | **Implemented** |
| M4 Durable HITL + Postgres Checkpoint | **Implemented** |
| M5 Reproducible Incident Lab | **Implemented** |
| M6 Historical Incident Memory / Hybrid RAG | **Implemented** |
| M7 MCP Capability Boundary | **Implemented** |
| M8 Multi-backend Governed Execution | **Implemented** |
| M8.5 Deployment Compatibility & Legacy Migration Bridge | **Implemented** |

The worker builds one operator-configured `ActionService` per iteration from the selected Mock or
Ansible backend and the enabled Target allowlist. It injects that same policy/executor boundary
into both ordinary Operations and LangGraph workflows; workflow code never selects a backend and
fails closed if the dependency is absent.

LangGraph uses stable `thread_id = workflow_id` identifiers. Development tests may use an in-memory
saver; the demo uses PostgreSQL checkpoint persistence and identity-bound approval/resume.

The legacy SSH and service-script runtime was removed in M1B. Ansible may use SSH internally
according to operator-owned inventory, but that is not part of the Agent/API contract.

## Roadmap

| Milestone | Status |
| --- | --- |
| M1A – M8.5 | **Implemented** (see Current Status) |
| Local Demo Closeout | **Implemented** |
| M8 Harness Multi-backend Execution | **Implemented** |
| M8.5 Deployment Compatibility | **Implemented** |
| Portfolio v1.0 evidence and release closeout | **Current stable release** |
| M9 GitOps Change Workflow | Future work / next engineering milestone |
| M10 Risk Reviewer / Advanced Eval | Future work |
| M11 Agent Observability / Production Hardening | Future work |

### Portfolio Entry Point

The canonical local demonstration remains the stable public portfolio entry point. M8 governed
multi-backend execution and the M8.5 synthetic legacy-environment migration bridge are implemented.

## Why this project is different

- **Not a chatbot wrapper** — the LLM performs one narrow, structured transformation: bounded
  Evidence → validated investigation result.
- **Evidence-driven** — the model can only reference real, deduplicated Incident Evidence IDs.
- **Explicit LangGraph workflow** — investigation is a testable state machine, not an open-ended
  prompt loop.
- **Deterministic authorization boundary** — policy, allowlists, and approval are code, not
  model output.
- **Infrastructure-safe execution** — typed adapters with fixed mappings; no shell, no raw
  query language, no caller-controlled paths.
- **Evaluation and auditability** — deterministic evaluation fixtures, safety cases, and an
  append-only audit trail are first-class.

## Documentation

- [Documentation index](docs/README.md) — English
- [文档索引](docs/zh-CN/README.md) — 简体中文
- [Architecture](docs/architecture.md)
- [Safety Model](docs/safety-model.md)
- [Roadmap](docs/roadmap.md)
- [Development guide](docs/development.md)
- [Testing strategy](docs/testing.md)
- [Portfolio benchmark](docs/evaluation/portfolio-benchmark.md)
- [Resume pack](docs/portfolio/resume.md)
- [Interview guide](docs/portfolio/interview-guide.md)
- [Design docs](docs/design/)
- [Architecture decisions (ADR)](docs/adr/)
- [Interview notes](docs/interview/)
- [Learning map](docs/learning-map.md)
- [Translation policy](docs/translation-policy.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

License: see the repository `LICENSE` file supplied by the project owner.
