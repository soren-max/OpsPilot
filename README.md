# OpsPilot

**Agentic Incident Response Platform**

OpsPilot is an open-source project for evidence-driven, human-controlled incident response.
It is being built to help SRE and incident responders collect evidence, form explicit
hypotheses, propose structured actions, and execute approved changes through constrained
infrastructure adapters.

## Problem

General-purpose agents can produce plausible commands without possessing operational context
or authorization. OpsPilot separates assistance from authority: a model may propose a typed
action, but deterministic policy, target allowlists, approval, and an executor boundary decide
whether anything can run.

## Design Principles

- **Evidence Before Action** — investigate before proposing a change.
- **Least Privilege** — expose narrow capabilities, never an arbitrary shell.
- **Human Control** — state-changing actions require explicit approval.
- **Auditable by Design** — decisions, approvals, execution, and verification have durable
  domain boundaries.

## Architecture

```mermaid
flowchart TD
  User[User / Alert] --> Workflow[LangGraph Incident Workflow - Implemented]
  Workflow --> Capabilities[Prometheus / Loki / Ticket / Health - Implemented]
  Capabilities --> Evidence[Durable Evidence + provenance]
  Evidence --> Investigator[LLM Investigator - Implemented]
  Investigator --> Guard[Structured Output + Grounding Guard]
  Guard --> Action[Structured Action Proposal]
  Action --> Policy[Deterministic Policy - Implemented]
  Policy --> Approval[Human Approval Boundary - Partial]
  Approval --> Executor[ActionExecutor - Implemented]
  Executor --> Mock[Mock Adapter - Implemented]
  Executor --> Ansible[Ansible Adapter - Implemented]
  Ansible --> Infrastructure[Test Infrastructure]
```

The Action Safety Core uses:

```text
ActionRequest -> ActionPolicyEngine -> approval boundary -> ActionExecutor -> verification
```

No model output is passed to a shell, SSH client, inventory path, or playbook path.

## Safety Model

The LLM is a decision assistant, not an authorization authority. Read-only actions can be
allowed automatically. Service restarts are medium risk and remain blocked until approval.
Unknown actions, unknown targets, malformed parameters, and extra fields fail closed.

See [Safety Model](docs/safety-model.md).

## Current Status

- **Implemented:** strict structured actions, deterministic risk policy, dependency-injected
  executor port, Mock adapter, fixed-mapping Ansible adapter, backend/frontend regression base.
- **Implemented:** portable operation runtime, logical Targets, controlled readiness metadata,
  and removal of application-level transport configuration.
- **Implemented:** M2 LangGraph incident workflow, serializable reference state, conditional
  routing, WorkflowRun metadata, deterministic investigation, audit trace, and API/UI progress.
- **Implemented:** M2.1 shared operator-configured execution boundary and fail-closed workflow
  runtime wiring.
- **Implemented:** M3A typed and bounded Prometheus, Loki, Ticket, and Service Health capability
  ports with provenance-preserving Incident Evidence collection.
- **Implemented:** M3B provider-neutral structured reasoning, bounded evidence context, grounded
  LLM investigation, prompt-injection defenses, and deterministic evaluation fixtures.
- **Planned:** durable HITL, MCP, RAG, and incident lab.

The worker builds one operator-configured `ActionService` per iteration from the selected Mock or
Ansible backend and the enabled Target allowlist. It injects that same policy/executor boundary
into both ordinary Operations and LangGraph workflows; workflow code never selects a backend and
fails closed if the dependency is absent.

M2 injects LangGraph's own `BaseCheckpointSaver` port and uses `InMemorySaver` for development and
tests. Stable LangGraph threads use `thread_id = workflow_id`, but process restarts lose memory
checkpoints. Production-grade Postgres checkpoint persistence and authenticated approval/resume
belong to M4.

The legacy SSH and service-script runtime has been removed in M1B. Ansible may use SSH internally
according to operator-owned inventory, but that is not part of the Agent/API contract.

## Quick Start

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/), and Node.js 22+.

```bash
uv sync --project backend --extra dev
uv run --project backend pytest backend/tests

cd frontend
npm ci
npm test
npm run dev
```

Copy `.env.example` to `.env` and replace every placeholder before starting the API. Never
commit `.env`.

## Development and Testing

- [Development guide](docs/development.md)
- [Testing strategy](docs/testing.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Contributing](CONTRIBUTING.md)

## Documentation

- [Learning map](docs/learning-map.md)
- [Interview notes](docs/interview/)
- [Architecture decisions](docs/adr/)
- [Security policy](SECURITY.md)

License: see the repository `LICENSE` file supplied by the project owner.
