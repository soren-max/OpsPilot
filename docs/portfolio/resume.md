# Resume Pack

All claims refer to this public, synthetic portfolio repository. Replace no number without rerunning
`make portfolio-benchmark`; do not describe it as production-deployed.

## 中文

### 项目简介

OpsPilot 是一个 evidence-grounded 事件响应工程原型：聚合实时可观测证据与历史事件记忆，
由 Investigator 生成结构化处置建议，再经确定性策略、持久化 HITL、受治理执行与独立验证
完成可审计闭环。默认演示完全离线且可重复。

### 3 bullets

- 设计 Evidence-grounded incident workflow，隔离当前 Evidence 与历史 Knowledge，以严格
  Evidence ID grounding 和结构化 Action 防止模型输出直接进入执行面；离线安全矩阵覆盖
  15 个攻击场景，当前 benchmark 为 0 条意外执行路径。
- 基于 LangGraph + PostgreSQL 实现可恢复 HITL，以业务状态、checkpoint、幂等指纹和
  Transactional Outbox 分离控制流与外部副作用；覆盖重复审批/恢复、worker crash、UNKNOWN
  dispatch 与 reconciliation。
- 构建 Prometheus/Loki/Health/Ticket 证据采集、40 文档/12 查询的 Dense/Sparse/Hybrid RRF
  历史事件检索，以及 Ansible/Harness 受治理执行边界；本地 service-down 演示以真实 Ansible
  修复并独立验证。

### 4 bullets

- 将事件处理建模为 Evidence → Investigation → typed Action → Policy → HITL → Execution →
  Verification 的显式状态链，保留审计与 OTel 关联，不持久化隐藏推理。
- 实现 provider-neutral LLM Investigator 与离线 deterministic baseline；模型只能建议，授权由
  target allowlist、确定性 risk policy 和身份绑定审批决定。
- 以 Transactional Outbox、UNKNOWN 状态和 Reconciler 处理外部系统“已接受但本地丢响应”，
  避免不安全盲重试，并证明 execution success 不等于 incident resolved。
- 用 MCP 作为 typed interoperability boundary、用 Ansible-over-SSH 兼容 synthetic legacy host；
  API/Agent 无法选择 backend、inventory、playbook、script 或 shell command。

### 技术栈与指标

Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, LangGraph, Ansible, Prometheus, Loki, Qdrant,
MCP, OpenTelemetry, React, TypeScript, Docker Compose. 当前 artifact 收集 320 个 backend tests、
28 个 frontend tests、4 个 Lab scenarios；精确检索与安全指标见 generated artifact。

## English

### Project summary

OpsPilot is an evidence-grounded incident-response engineering prototype. It combines current
observability evidence with separate historical incident memory, produces typed proposals, and
routes them through deterministic policy, durable HITL, governed execution, independent
verification, audit, and telemetry. Its canonical demo is offline and synthetic.

### 3 bullets

- Designed an evidence-grounded incident workflow that separates current Evidence from historical
  Knowledge and prevents model text from reaching execution through strict evidence-ID grounding
  and typed Actions; the offline matrix covers 15 adversarial paths with zero unexpected paths in
  the generated benchmark.
- Implemented durable HITL with LangGraph/PostgreSQL while separating business state, checkpoints,
  idempotency fingerprints, and a Transactional Outbox; tested duplicate decisions/resumes,
  dispatcher crashes, UNKNOWN side effects, and reconciliation.
- Built typed Prometheus/Loki/Health/Ticket collection, a 40-document/12-query Dense/Sparse/Hybrid
  RRF incident-memory benchmark, and governed Ansible/Harness boundaries with independent health
  verification.

### 4 bullets

- Modeled response as an explicit Evidence → Investigation → Action → Policy → HITL → Execution →
  Verification lifecycle with correlated audit and OpenTelemetry data, without stored hidden
  reasoning.
- Added provider-neutral structured LLM investigation plus an offline deterministic baseline; the
  model proposes while allowlists, deterministic risk rules, and identity-bound approval authorize.
- Used a Transactional Outbox, explicit UNKNOWN state, and reconciliation to handle remote acceptance
  with a lost local response without blind duplicate dispatch.
- Exposed typed MCP interoperability and bounded synthetic Ansible-over-SSH compatibility while
  keeping backend, inventory, playbook, script, and command selection operator-owned.

### Tech stack and metrics

Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, LangGraph, Ansible, Prometheus, Loki, Qdrant,
MCP, OpenTelemetry, React, TypeScript, and Docker Compose. The generated artifact currently collects
320 backend tests, 28 frontend tests, four Lab scenarios, and the exact quality/security metrics.

