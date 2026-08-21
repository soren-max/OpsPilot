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
| M8 Multi-backend Execution | Planned | Ansible plus a future Harness backend |
| M9 GitOps Change Workflow | Planned | Governed configuration and deployment change |
| M10 Risk Reviewer & Evaluation | Planned | Advisory risk review and safety evaluation |
| M11 Agent Observability | Planned | Workflow traces and operational telemetry |

Harness and GitOps in M8/M9 are future enhancements. M1B includes no Harness SDK, production
backend, or simulated implementation.

## Current Portfolio Pause Point

**Local Demo Closeout after M7** is the current stable portfolio pause point. M1–M7 are implemented;
the canonical demonstration focuses on the complete evidence, durable approval, Ansible remediation,
and verification path. Historical Memory and MCP remain optional advanced demonstrations.

Next: **M8 Multi-backend Governed Execution**.
