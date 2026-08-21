# 路线图（Roadmap）

[English](../roadmap.md) | [简体中文](roadmap.md)

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
| M5 Local Incident Lab | Done | Reproducible incident scenarios |
| M6 Historical Incident Memory / RAG | Done | Curated hybrid retrieval with provenance |
| M7 MCP Capability Boundary | Done | Optional interoperable capability boundary |
| M8 Multi-backend Execution | Planned | Ansible plus a future Harness backend |
| M9 GitOps Change Workflow | Planned | Governed configuration and deployment change |
| M10 Risk Reviewer & Evaluation | Planned | Advisory risk review and safety evaluation |
| M11 Agent Observability | Planned | Workflow traces and operational telemetry |

M8/M9 中的 Harness 与 GitOps 是未来的增强。M1B 不包含 Harness SDK、生产后端或模拟实现。

## 当前 Portfolio 暂停点

**M7 之后的 Local Demo Closeout** 是当前稳定公开基线。M1–M7 已实现；
下一工程里程碑是 **M8 —— Multi-backend Governed Execution**。
