# OpsPilot

[English](README.md) | [简体中文](README.zh-CN.md)

**Agentic Incident Response Platform**

OpsPilot is an open-source project for evidence-driven, human-controlled incident response.
It is built to help SRE and incident responders collect evidence, form explicit hypotheses,
propose structured actions, and execute approved changes through constrained infrastructure
adapters — never through an arbitrary shell.

The current milestone (M6) adds source-linked Historical Incident Memory to the complete
**Observability → Evidence → LLM Investigator → Grounding Guard → Structured Action → Policy →
Durable Human Approval → Ansible → Verification** pipeline against a reproducible local Lab.
The default walkthrough is deterministic and requires no model API key.

## Historical Incident Memory

Only resolved/closed, diagnosed incidents are deterministically projected and explicitly indexed.
Qdrant combines dense and sparse retrieval with RRF. Related incidents appear as **Historical
Context**, separately from current Evidence; similarity is not confidence and cannot authorize an
action. Run `make memory-eval` for the committed 40-record retrieval benchmark.

## Live Incident Lab

In about 30 seconds of terminal output, `make lab-demo` explains the operational story:

**Fault → real Prometheus/Loki/Health Evidence → deterministic investigation → approval → fixed
Ansible remediation → verified recovery.**

The existing fixture demo (`make demo`) is the fastest zero-service walkthrough. The Live Lab
(`make lab-demo`) starts disposable Docker services and proves the actual integration boundaries.
See [lab/README.md](lab/README.md). Neither mode is presented as production deployment.

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
  Policy --> Approval{Human Approval<br/>M3: WAITING_APPROVAL stop point<br/>M4: durable approval - Planned}
  Approval --> Executor[ActionExecutor<br/>Implemented]
  Executor --> Mock[Mock Adapter<br/>Implemented]
  Executor --> Ansible[Ansible Adapter<br/>Implemented]
  Ansible --> Infra[Target Infrastructure]
  subgraph Planned[M4 and beyond]
    direction LR
    Postgres[(Postgres Checkpoint<br/>Planned)]
    HITL[Durable HITL Resume<br/>Planned]
    Harness[Harness Backend<br/>Planned]
    RAG[RAG / Playbook Memory<br/>Planned]
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
- Audit / evaluation foundation: evaluation fixtures, safety cases, secret scan in CI

**Planned (not yet implemented):**

- MCP capability boundary (`M7`)
- Harness multi-backend execution (`M8`)
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
| M4 Durable HITL + Postgres Checkpoint | **Planned — next milestone** |

The worker builds one operator-configured `ActionService` per iteration from the selected Mock or
Ansible backend and the enabled Target allowlist. It injects that same policy/executor boundary
into both ordinary Operations and LangGraph workflows; workflow code never selects a backend and
fails closed if the dependency is absent.

M2 injects LangGraph's own `BaseCheckpointSaver` port and uses `InMemorySaver` for development and
tests. Stable LangGraph threads use `thread_id = workflow_id`, but process restarts lose memory
checkpoints. Production-grade Postgres checkpoint persistence and authenticated approval/resume
belong to M4.

The legacy SSH and service-script runtime was removed in M1B. Ansible may use SSH internally
according to operator-owned inventory, but that is not part of the Agent/API contract.

## Roadmap

| Milestone | Status |
| --- | --- |
| M1A – M3B | **Done** (see Current Status) |
| **M4 Durable HITL + Postgres Checkpoint** | **Next** |
| M5 Incident Lab | Future |
| M6 Playbook Memory / RAG | Future |
| M7 MCP | Future |
| M8 Harness Multi-backend Execution | Future |
| M9 GitOps | Future |
| M10 Risk Reviewer / Evaluation | Future |
| M11 Agent Observability | Future |

### Current Pause Point

**M3.5 represents the current stable portfolio milestone.** The project intentionally pauses new
core features here: the evidence-grounded investigation pipeline is complete, documented, and
tested, and the boundary before mutating execution is explicit. The next engineering milestone is
**M4 — Durable HITL + Postgres Checkpoint**.

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
- [Design docs](docs/design/)
- [Architecture decisions (ADR)](docs/adr/)
- [Interview notes](docs/interview/)
- [Learning map](docs/learning-map.md)
- [Translation policy](docs/translation-policy.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

License: see the repository `LICENSE` file supplied by the project owner.
