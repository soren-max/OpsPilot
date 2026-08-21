# 路线图（Roadmap）

M8 Multi-Backend Governed Execution 已完成；下一阶段是 M9 GitOps Change Workflow。

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
| M4 Durable HITL + Checkpoint | Planned | Identity-bound approval and resumable state |
| M5 Local Incident Lab | Planned | Reproducible incident scenarios |
| M6 Playbook Memory / RAG | Planned | Curated retrieval with provenance |
| M7 MCP Capability Boundary | Planned | Optional interoperable capability boundary |
| M8 Multi-backend Execution | Planned | Ansible plus a future Harness backend |
| M9 GitOps Change Workflow | Planned | Governed configuration and deployment change |
| M10 Risk Reviewer & Evaluation | Planned | Advisory risk review and safety evaluation |
| M11 Agent Observability | Planned | Workflow traces and operational telemetry |

M8/M9 中的 Harness 与 GitOps 是未来的增强。M1B 不包含 Harness SDK、生产后端或模拟实现。

## 当前暂停点（Current Pause Point）

**M3B 是当前稳定的组合里程碑。** 新核心功能在此暂停：证据约束的调查流水线已经完整、有文档、
有测试，变更执行前的边界是显式的。下一个工程里程碑是 **M4 —— Durable HITL + Postgres
Checkpoint**（身份绑定审批与可恢复状态）。
