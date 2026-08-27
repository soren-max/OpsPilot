# Roadmap

| Milestone | Status | Scope |
| --- | --- | --- |
| M1A Action Safety Core | Done | Structured actions, deterministic policy, controlled adapters |
| M1B Portable Execution Boundary | Done | Runtime migration and legacy transport removal |
| M1C Incident Domain + AuditEvent | Done | Durable incident, evidence, audit timeline, and knowledge projection |
| M2 LangGraph Incident Workflow | Done | Explicit incident state machine |
| M2.1 Workflow Runtime Hardening | Done | Shared configured execution boundary and fail-closed workflow wiring |
| M3A Observability & Ticket Capabilities | Implemented | Typed, bounded read-only evidence ports and adapters |
| M3B LLM Investigator | Implemented | Evidence-grounded structured investigation with deterministic authorization |
| M4 Durable HITL + Checkpoint | Done | Identity-bound approval and resumable state |
| M5 Local Incident Lab | Done | Reproducible live telemetry, failure, approval, and recovery scenarios |
| M6 Historical Incident Memory / RAG | Done | Hybrid retrieval with provenance and eval |
| M7 MCP Capability Boundary | Done | MCP 2026-07-28 typed interoperability and governed proposals |
| M8 Multi-Backend Governed Execution | Done | Mock, Ansible, Harness, outbox, reconciliation |
| M8.5 Deployment Compatibility | Next | Typed profiles and a synthetic legacy-environment migration bridge |
| M9 GitOps Change Workflow | Planned | Governed configuration and deployment change |
| M10 Risk Reviewer & Evaluation | Planned | Advisory risk review and safety evaluation |
| M11 Agent Observability | Planned | Workflow traces and operational telemetry |

M8 implements the governed Harness reference backend. M8.5 demonstrates bounded integration with
traditional SSH-managed test environments without restoring the removed ServiceSSH abstraction.

## Portfolio Entry Point

The canonical local demo remains the stable portfolio entry point. M1–M8 are implemented; the
demonstration focuses on evidence, durable approval, governed execution, and independent
verification. Historical Memory and MCP remain optional advanced demonstrations.

Next: **M8.5 Deployment Compatibility & Legacy Migration Bridge**.
