# 路线图（Roadmap）

M8 Multi-Backend Governed Execution 已完成；下一阶段是
M8.5 Deployment Compatibility & Legacy Migration Bridge。

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
| M8 Multi-backend Execution | Done | Mock, Ansible, Harness, outbox, reconciliation |
| M8.5 Deployment Compatibility | Next | 类型化 Profile 与合成遗留环境迁移桥 |
| M9 GitOps Change Workflow | Planned | Governed configuration and deployment change |
| M10 Risk Reviewer & Evaluation | Planned | Advisory risk review and safety evaluation |
| M11 Agent Observability | Planned | Workflow traces and operational telemetry |

M8 已实现受治理的 Harness 参考后端。M8.5 将演示如何在不恢复 ServiceSSH 抽象的
前提下，安全集成传统 SSH 管理的测试环境。

## Portfolio 入口

标准本地演示仍是稳定的公开 Portfolio 入口。M1–M8 已实现；
下一工程里程碑是 **M8.5 Deployment Compatibility & Legacy Migration Bridge**。
