# OpsPilot 中文文档

[English](../README.md) | [简体中文](README.md)

本目录是 OpsPilot 的中文文档索引。英文文档是 canonical（权威）版本，中文核心文档跟踪主要架构变更，并随里程碑推进与英文保持同步。

## Project Tour

新人和面试复盘建议按以下顺序阅读：

1. [架构](architecture.md)
2. [安全模型](safety-model.md)
3. [Incident 工作流](design/langgraph-incident-workflow.md)
4. [可观测性能力](design/observability-capabilities.md)
5. [LLM 调查器](design/llm-investigator.md)
6. [路线图](roadmap.md)

可运行演示与录制方式见英文 [Demo Guide](../demo.md)，ADR 汇总见英文
[ADR Index](../adr/README.md)。

## 核心文档

- [架构（Architecture）](architecture.md) — 系统分层总览：LangGraph Incident 工作流、类型化能力端口、Incident Evidence、LLM 调查器与 Action Safety Core（对应英文 [architecture.md](../architecture.md)）。
- [安全模型（Safety Model）](safety-model.md) — LLM 只是决策助手而非授权主体：只读动作可自动放行，重启等中风险动作必须审批，未知动作、未知目标与非法参数一律 fail-closed。
- [路线图（Roadmap）](roadmap.md) — 里程碑一览：M1A–M3B 均已完成（M1A 动作安全核心 → M3B LLM 调查器），M4（Durable HITL + Postgres Checkpoint）是下一个工程里程碑；RAG、MCP、Harness、GitOps 等仍在计划中。
- [开发指南（Development）](development.md) — 本地环境搭建、依赖管理（Python 3.13 / uv / Node 22+）与开发约定。
- [测试策略（Testing）](testing.md) — 后端/前端回归基线、确定性动作安全测试与评估夹具的使用方式。

## 设计文档

- [可观测性能力（Observability Capabilities）](design/observability-capabilities.md) — M3A 的类型化、有界只读证据端口（Metrics / Logs / Ticket / Service Health）与适配器设计。
- [LLM 调查器（LLM Investigator）](design/llm-investigator.md) — M3B 的单一 AI 能力：把有界、持久的 Incident Evidence 转换为严格校验的 `InvestigationResult`。
- [LangGraph Incident 工作流（LangGraph Incident Workflow）](design/langgraph-incident-workflow.md) — M2 用确定性 LangGraph `StateGraph` 组合既有 Incident 与 Action 应用边界。

## 面试笔记

- [面试笔记中文索引（Interview Notes）](interview/README.md) — 19 篇英文面试笔记的主题聚类索引与中文摘要，便于复习定位。

## 英文原版文档（English only）

以下文档保持英文原版，未翻译：

- [ADR 0001: Structured Actions over Arbitrary Shell](../adr/0001-structured-actions-over-arbitrary-shell.md) — English only
- [ADR 0002: Deterministic Policy before LLM Risk Review](../adr/0002-deterministic-policy-before-llm-risk-review.md) — English only
- [ADR 0003: Ansible as Infrastructure Execution Adapter](../adr/0003-ansible-as-infrastructure-execution-adapter.md) — English only
- [ADR 0004: Separate remediation from governed change](../adr/0004-separate-remediation-from-governed-change.md) — English only
- [ADR 0005: Separate domain state from workflow checkpoints](../adr/0005-separate-domain-state-from-workflow-checkpoint.md) — English only
- [ADR 0006: Typed Observability Queries over Arbitrary Query Languages](../adr/0006-typed-observability-queries-over-arbitrary-query-language.md) — English only
- [ADR 0007: LLM reasoning with deterministic authorization](../adr/0007-llm-reasoning-with-deterministic-authorization.md) — English only
- [Interview notes 正文](../interview/README.md) — English only（中文主题索引见 [interview/README.md](interview/README.md)）
- [Learning Map（学习地图）](../learning-map.md) — English only
- [Governed Execution（受控执行）](../design/governed-execution.md) — English only
- [Incident Memory and RAG（Incident 记忆与 RAG）](../design/incident-memory-and-rag.md) — English only
- [SECURITY.md（安全策略）](../../SECURITY.md) — English only
- [CONTRIBUTING.md（贡献指南）](../../CONTRIBUTING.md) — English only
