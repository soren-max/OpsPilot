# OpsPilot Documentation

[English](README.md) | [简体中文](zh-CN/README.md)

This is the index for the OpsPilot documentation. English is the canonical language: docs are
written and maintained in English first, and Simplified Chinese mirrors live under `docs/zh-CN/`
for the core docs. See the [Translation Policy](translation-policy.md) for how the two trees stay
in sync and which docs are intentionally English-only.

## Project Tour

New readers can follow this path for a concise architecture and interview walkthrough:

1. [Architecture](architecture.md) — layers, boundaries, and component responsibilities.
2. [Safety Model](safety-model.md) — how authority stays deterministic and human-controlled.
3. [Incident Workflow](design/langgraph-incident-workflow.md) — explicit LangGraph state flow.
4. [Observability Capabilities](design/observability-capabilities.md) — typed evidence sources.
5. [LLM Investigator](design/llm-investigator.md) — grounded reasoning without authority.
6. [Roadmap](roadmap.md) — implemented scope through M8.5 and next options.
7. [Deployment Compatibility](design/deployment-compatibility.md) — safe legacy SSH migration.

For a runnable tour, use the [Offline Demo and Recording Guide](demo.md).

## Architecture

- [Architecture](architecture.md) — system overview and component boundaries (简体中文: [zh-CN/architecture.md](zh-CN/architecture.md))

## Safety

- [Safety Model](safety-model.md) — deterministic policy, approval, and fail-closed behavior (简体中文: [zh-CN/safety-model.md](zh-CN/safety-model.md))
- [Security Policy](../SECURITY.md) — how to report security issues

## Roadmap

- [Roadmap](roadmap.md) — milestone plan through M8.5 and beyond (简体中文: [zh-CN/roadmap.md](zh-CN/roadmap.md))

## Development

- [Development Guide](development.md) — environment setup and backend/frontend layout (简体中文: [zh-CN/development.md](zh-CN/development.md))
- [Contributing](../CONTRIBUTING.md) — contribution workflow and standards

## Testing

- [Testing](testing.md) — test strategy and regression base (简体中文: [zh-CN/testing.md](zh-CN/testing.md))

## Design Docs

- [Deployment Compatibility](design/deployment-compatibility.md) — M8.5 typed profiles, Ansible over SSH, verification and readiness
- [Legacy Environment Migration Guide](migration/legacy-environment-guide.md) — synthetic-to-private migration steps
- [Private Adapter Boundary](migration/private-adapter-boundary.md) — public code versus private deployment knowledge
- [Observability and Ticket Capabilities](design/observability-capabilities.md) — typed, bounded capability ports (简体中文: [zh-CN/design/observability-capabilities.md](zh-CN/design/observability-capabilities.md))
- [LLM Investigator](design/llm-investigator.md) — bounded-evidence to structured investigation (简体中文: [zh-CN/design/llm-investigator.md](zh-CN/design/llm-investigator.md))
- [LangGraph Incident Workflow](design/langgraph-incident-workflow.md) — deterministic workflow orchestration (简体中文: [zh-CN/design/langgraph-incident-workflow.md](zh-CN/design/langgraph-incident-workflow.md))
- [Governed Execution](design/governed-execution-plane.md) — implemented M8 routing, outbox and reconciliation
- [Incident Memory and RAG](design/incident-memory-and-rag.md) — English only (projection and hybrid retrieval implemented)
- [Portfolio Benchmark](evaluation/portfolio-benchmark.md) — generated evidence entry point
- [Portfolio Demo](demo/portfolio-demo.md) — canonical 3–5 minute walkthrough
- [Resume Pack](portfolio/resume.md) and [Interview Guide](portfolio/interview-guide.md)

## Architecture Decision Records (ADR)

All ADRs are English only.

- [ADR index](adr/README.md) — titles, statuses, and one-line summaries

- [ADR 0001: Structured Actions over Arbitrary Shell](adr/0001-structured-actions-over-arbitrary-shell.md)
- [ADR 0002: Deterministic Policy before LLM Risk Review](adr/0002-deterministic-policy-before-llm-risk-review.md)
- [ADR 0003: Ansible as Infrastructure Execution Adapter](adr/0003-ansible-as-infrastructure-execution-adapter.md)
- [ADR 0004: Separate remediation from governed change](adr/0004-separate-remediation-from-governed-change.md)
- [ADR 0005: Separate domain state from workflow checkpoints](adr/0005-separate-domain-state-from-workflow-checkpoint.md)
- [ADR 0006: Typed Observability Queries over Arbitrary Query Languages](adr/0006-typed-observability-queries-over-arbitrary-query-language.md)
- [ADR 0007: LLM reasoning with deterministic authorization](adr/0007-llm-reasoning-with-deterministic-authorization.md)
- [ADR 0013: SSH is an infrastructure detail](adr/0013-ssh-is-an-infrastructure-detail.md)
- [ADR 0014: Legacy migration uses Strangler adapters](adr/0014-legacy-migration-uses-strangler-adapters.md)

## Interview Notes

- [Interview Notes index](interview/README.md) — topic-by-topic design notes. English only.

## Learning Map

- [Learning Map](learning-map.md) — suggested reading order for newcomers. English only.

## Translation Policy

- [Translation Policy](translation-policy.md) — how English and Chinese docs stay in sync.

## English-only docs

The following are intentionally English only and do not require Chinese translation:
ADR records, interview notes, the learning map, the Governed Execution design doc, and the
Incident Memory and RAG design doc.
