# OpsPilot

[English](README.md) | [简体中文](README.zh-CN.md)

**智能体事故响应平台（Agentic Incident Response Platform）**

OpsPilot 是一个开源的、以证据驱动（Evidence-driven）且由人控制的事故响应项目。它帮助
SRE 与事故响应人员收集证据、形成明确的假设、提出结构化动作（Structured Action），并经由
受限的基础设施适配器执行经过审批的变更——而不是通过任意 shell。

当前里程碑（M3B）是一个稳定的项目收口点：项目完整展示了
**可观测性 → 证据 → LLM 调查器 → 证据约束（Evidence Grounding）→ 结构化动作 → 策略 →
人工审批 → 执行器** 这条流水线，并刻意在「未获得持久化审批就执行变更动作」之前停下。
持久化的审批与恢复是下一个里程碑（M4）。

## 为什么需要 OpsPilot

通用智能体会生成看似合理、但缺乏运维上下文与授权的命令。OpsPilot 把「辅助」与「授权」
彻底分离：

- 模型可以**提议**一个类型化动作，但能否真正**执行**由确定性策略、目标白名单、审批与
  执行器边界决定。
- LLM 是决策助手，不是授权主体。它的输出要经过校验、证据约束和确定性控制的门禁。
- 证据、诊断、提议、审批、执行、验证——每一步都是显式、可审计、可测试的。

## 核心原则

- **证据先于动作（Evidence Before Action）** —— 先调查，再提议变更。
- **最小权限（Least Privilege）** —— 只暴露狭窄的类型化能力，绝不暴露任意 shell。
- **人工控制（Human Control）** —— 改变状态的动作用于必须显式审批。
- **默认可审计（Auditable by Design）** —— 决策、审批、执行、验证都有持久的领域边界。
- **确定性基线（Deterministic Baseline）** —— 离线调查器让系统可复现、对 CI 友好；
  LLM 是运维人员显式选择的增强，不是隐藏依赖。

## 架构

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

动作安全核心（Action Safety Core）为：

```text
ActionRequest -> ActionPolicyEngine -> approval boundary -> ActionExecutor -> verification
```

任何模型输出都不会被传给 shell、SSH 客户端、inventory 路径或 playbook 路径。

## 当前能力

**已实现（Implemented）：**

- LangGraph 事故工作流，显式、可 JSON 序列化的状态（`M2`、`M2.1`）
- 类型化、有边界的 Prometheus / Loki 能力适配器，以及 Ticket / Service Health 端口（`M3A`）
- 持久化 Incident、Evidence 与 append-only AuditEvent 领域模型（`M1C`）
- 证据约束（Evidence Grounding）：校验 Evidence ID、限制上下文（`M3B`）
- Provider 无关端口背后的 OpenAI 结构化调查器（`M3B`）
- 确定性离线调查基线（无需 API key）
- 确定性策略引擎：目标白名单与 fail-closed 规则
- 依赖注入端口背后的 Mock 与固定映射 Ansible 执行器（`M1A`/`M1B`）
- 审计 / 评估基础：评估夹具、安全用例、CI 中的 secret 扫描

**计划中（Planned，尚未实现）：**

- 持久化 HITL：Postgres checkpoint 与恢复（`M4`）
- Incident Lab（`M5`）
- RAG / playbook 记忆（`M6`）
- MCP 能力边界（`M7`）
- Harness 多后端执行（`M8`）
- GitOps 受治理变更工作流（`M9`）
- 高级评估与智能体可观测性（`M10`/`M11`）

## 安全模型

LLM 是决策助手，不是授权主体。只读动作可以自动放行；服务重启属于中风险，在获得审批前
保持阻塞。未知动作、未知目标、畸形参数与多余字段一律 fail closed。

### 安全要点（Safety Highlights）

- **无任意 shell** —— 只有带严格 schema 的枚举型结构化动作。
- **无任意 PromQL / LogQL** —— 查询模板由应用拥有。
- **Evidence ID 经过校验** —— 模型只能引用当前 Incident 中真实存在的证据，无法虚构 ID。
- **被提示注入的日志/工单视为不可信数据** —— 证据按数据序列化，生成之后还有 schema、
  证据约束、策略等可强制执行的防线。
- **LLM 不能授权执行** —— 策略与审批都是确定性的。
- **变更类动作必须审批** —— 中风险动作停在 `WAITING_APPROVAL`。
- **执行器由运维配置选择** —— 工作流代码从不选择后端，依赖缺失时 fail closed。
- **不持久化隐藏的思维链（Chain-of-Thought）** —— 只保留可审计的结论。
- **审计元数据不泄漏密钥** —— 审计中不含凭据、原始 prompt 或原始证据正文。

参见 [安全模型](docs/zh-CN/safety-model.md)。

## 示例事故流程

一条确定性的演示路径贯穿整条流水线：

```text
SERVICE_UP = 0
+ error logs
+ related ticket
+ health unavailable
        ↓
证据收集                      （M3A：有界、类型化、保留来源）
        ↓
LLM 证据约束诊断               （M3B：严格 schema + Evidence ID 校验）
        ↓
restart_service 提议
        ↓
MEDIUM risk                  （确定性策略）
        ↓
WAITING_APPROVAL             ← M3 在变更动作之前停下
```

> **当前 M3 行为：** 工作流在 `WAITING_APPROVAL` 停下，任何变更动作都不会被执行。
> 持久化的审批与恢复在 **M4** 实现——不在本里程碑内。只读动作（例如状态检查）可以自动放行。

## 快速开始

支持两种模式；**离线模式不需要付费 API**。

### 离线 / 确定性模式（默认）

前置条件：Python 3.13、[uv](https://docs.astral.sh/uv/)、Node.js 22+。

```bash
uv sync --project backend --extra dev
uv run --project backend pytest backend/tests

cd frontend
npm ci
npm test
npm run dev
```

默认 `LLM_MODE=deterministic`（见 `.env.example`）即完全离线基线：不需要
`OPENAI_API_KEY`，不发任何网络请求，CI 保持确定性。

### LLM 模式（可选）

在 `.env` 中配置（不要把 `.env` 提交到仓库）：

```bash
LLM_MODE=llm
LLM_PROVIDER=openai
LLM_MODEL=<模型名，例如 gpt-5-mini>
LLM_API_KEY=<你的 key>
```

LLM 模式需要有效的 `OPENAI_API_KEY` 与经运维确认的模型配置。Provider 失败是显式、可审计
的——不会悄悄回退到确定性基线。

把 `.env.example` 复制为 `.env`，并在启动 API 前替换所有占位符。

## 当前状态

| 里程碑 | 状态 |
| --- | --- |
| M1A Action Safety Core | **已实现** |
| M1B Portable Execution Boundary | **已实现** |
| M1C Incident Domain + Audit | **已实现** |
| M2 LangGraph Incident Workflow | **已实现** |
| M2.1 Workflow Runtime Hardening | **已实现** |
| M3A Observability Capabilities | **已实现** |
| M3B Evidence-Grounded LLM Investigator | **已实现** |
| M4 Durable HITL + Postgres Checkpoint | **计划中 —— 下一里程碑** |

Worker 每次迭代从选中的 Mock 或 Ansible 后端与启用的 Target 白名单构建一个由运维配置的
`ActionService`，并把同一个策略/执行器边界注入普通 Operations 与 LangGraph 工作流；工作流
代码从不选择后端，依赖缺失时 fail closed。

M2 直接注入 LangGraph 自带的 `BaseCheckpointSaver` 端口，开发与测试使用 `InMemorySaver`。
稳定的 LangGraph 线程使用 `thread_id = workflow_id`，但进程重启会丢失内存 checkpoint。
生产级 Postgres checkpoint 持久化与带身份认证的审批/恢复属于 M4。

M1B 已移除遗留的 SSH 与服务脚本运行时。Ansible 可以按运维自有的 inventory 在内部使用 SSH，
但那不属于 Agent/API 契约。

## 路线图

| 里程碑 | 状态 |
| --- | --- |
| M1A – M3B | **已完成**（见当前状态） |
| **M4 Durable HITL + Postgres Checkpoint** | **下一里程碑** |
| M5 Incident Lab | 未来 |
| M6 Playbook Memory / RAG | 未来 |
| M7 MCP | 未来 |
| M8 Harness Multi-backend Execution | 未来 |
| M9 GitOps | 未来 |
| M10 Risk Reviewer / Evaluation | 未来 |
| M11 Agent Observability | 未来 |

### 当前暂停点（Current Pause Point）

**M3B 是当前稳定的组合里程碑。** 项目在此刻意暂停新增核心功能：证据约束的调查流水线已
完整、有文档、有测试，变更执行前的边界是显式的。下一个工程里程碑是
**M4 —— Durable HITL + Postgres Checkpoint**。

## 这个项目有什么不同

- **不是聊天机器人包装** —— LLM 只做一次窄变换：有界证据 → 经过校验的调查结果。
- **证据驱动** —— 模型只能引用真实、去重过的 Incident Evidence ID。
- **显式 LangGraph 工作流** —— 调查是一个可测试的状态机，而不是开放式 prompt 循环。
- **确定性授权边界** —— 策略、白名单、审批都是代码，不是模型输出。
- **基础设施安全的执行** —— 类型化适配器 + 固定映射；没有 shell、没有裸查询语言、
  没有调用方可控的路径。
- **可评估、可审计** —— 确定性评估夹具、安全用例、append-only 审计轨迹都是头等公民。

## 文档

- [Documentation index](docs/README.md) — English
- [文档索引](docs/zh-CN/README.md) — 简体中文
- [架构](docs/zh-CN/architecture.md)
- [安全模型](docs/zh-CN/safety-model.md)
- [路线图](docs/zh-CN/roadmap.md)
- [开发指南](docs/zh-CN/development.md)
- [测试策略](docs/zh-CN/testing.md)
- [设计文档](docs/zh-CN/design/)
- [ADR（架构决策记录）](docs/adr/) — English only
- [面试笔记索引](docs/zh-CN/interview/README.md)
- [翻译政策](docs/translation-policy.md)
- [安全政策](SECURITY.md)
- [参与贡献](CONTRIBUTING.md)

许可证：见仓库根目录 `LICENSE` 文件（由项目所有者提供）。
