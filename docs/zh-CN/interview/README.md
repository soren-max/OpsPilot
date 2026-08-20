# 面试笔记中文索引

[English](../../interview/README.md) | [简体中文](README.md)

这些面试笔记以英文撰写，正文暂不翻译；本页提供主题索引与中文摘要，便于复习定位。

> 注：`08-incident-domain.md` 与 `08-portable-execution-boundary.md` 共享 `08-` 前缀，这是历史编号遗留，未做重命名。笔记按主题聚类排列，编号仅表示撰写顺序。

## Agent 工作流

- **工具调用（Tool Calling）** — [`02-tool-calling.md`](../../interview/02-tool-calling.md) · 状态：**计划中（Planned）**
  未来能力端口将允许模型在窄能力与校验过的参数之间做选择，产出证据或结构化动作提案，从而限制模型权限、让观察显式化。

- **Agent 工作流（Agent Workflow）** — [`03-agent-workflow.md`](../../interview/03-agent-workflow.md) · 状态：**M2 已实现（Implemented in M2）**
  用显式状态机把调查表达为状态转移，而不是开放式的大段 prompt；M1C 提供 Incident / Evidence / Hypothesis / Diagnosis / AuditEvent 边界，M2 的 LangGraph 工作流将这些能力组合起来，并保持节点名与稳定业务状态分离。

- **Agent 安全（Agent Safety）** — [`04-agent-safety.md`](../../interview/04-agent-safety.md) · 状态：**部分实现（Partial）**
  安全由受限能力、确定性授权、人工审批与审计共同构成；`ActionPolicyEngine`、严格模型、目标白名单与适配器映射是 M1A 核心——"模型输出有用"并不等于"拥有运维权限"。

- **人工介入（Human in the Loop）** — [`05-hitl.md`](../../interview/05-hitl.md) · 状态：**部分实现（Partial）；M4 计划实现 durable interrupt/resume**
  HITL 在状态变更动作执行前暂停工作流，等待授权人审查确切动作；目前中风险策略会阻断执行直至审批，持久化的工作流中断与 checkpoint 集成计划在 M4 落地。

## LangGraph

- **LangGraph Incident 编排（LangGraph Incident Orchestration）** — [`11-langgraph.md`](../../interview/11-langgraph.md) · 状态：**M2 已实现（Implemented in M2）**
  用 StateGraph 表达具名阶段、确定性策略分支、副作用、暂停点与失败语义；M2 本身完全不使用 LLM——`DeterministicInvestigator` 直接产出结构化假设、诊断、动作提案、证据引用与置信度。

- **工作流持久化（Workflow Persistence）** — [`12-workflow-persistence.md`](../../interview/12-workflow-persistence.md) · 状态：**M2 边界已实现（Implemented boundary in M2）**
  `thread_id` 是 LangGraph 的稳定线程标识，映射到 `workflow_id` 而非随机请求 ID；checkpoint 只回答"图执行到哪里、持有哪些本地引用"，业务事实始终由应用服务写入 Incident 数据库。

## Incident 领域

- **Incident 领域（Incident Domain）** — [`08-incident-domain.md`](../../interview/08-incident-domain.md) · 状态：**M1C 已实现（Implemented in M1C）**
  Evidence 是一等公民：观察记录保留类型、来源、时间、provenance、采集器与稳定身份，可去重、可追溯、可审计；原始日志不落入 Incident 数据库，只保存有界摘录、摘要与指纹。

- **Incident 记忆（Incident Memory）** — [`10-incident-memory.md`](../../interview/10-incident-memory.md) · 状态：**M1C 知识投影已实现；M6 检索计划中（retrieval planned for M6）**
  `ActionRequest` 不携带 `incident_id`，让 Action 领域可复用于无 Incident 的运维场景，由应用层的 `IncidentActionLink` 关联；只有已解决/关闭的 Incident 才进入记忆，避免把进行中的竞争性假设当作权威历史索引。

## 审计

- **审计与事件模型（Audit and Event Model）** — [`09-audit-and-event-model.md`](../../interview/09-audit-and-event-model.md) · 状态：**M1C 已实现（Implemented in M1C）**
  审计历史只追加：ORM 的 update/delete 钩子拒绝变更，更正以新事件配合关联/因果 ID 表达；状态变更与审计事件在同一事务中提交，任一失败则整体回滚，保证"可审计的 Incident"。

## 可观测性

- **可观测性能力（Observability Capabilities）** — [`13-observability-capabilities.md`](../../interview/13-observability-capabilities.md) · 状态：**M3A 已实现（Implemented in M3A）**
  Metrics/Logs 端口接收有类型、有界的查询（如 `MetricQuery` 而非 PromQL），由适配器映射到受审模板后调用 Prometheus / Loki 的直接 HTTP API；LLM 不直接编写 PromQL/LogQL，租户与认证配置归运维所有。

## 证据约束（Evidence Grounding）

- **证据约束（Evidence Grounding）** — [`14-evidence-grounding.md`](../../interview/14-evidence-grounding.md) · 状态：**M3A/M3B 已实现（Implemented）**
  每条规范化观察都记录来源、来源引用、观测/采集时间、采集器、有界内容与去重指纹；原始日志不进入 Graph State——图状态只保存 Evidence ID，Incident 数据库持有有界业务记录，LLM 诊断必须返回证据 ID，经 Incident Evidence 追溯到源系统。

## LLM 调查器

- **LLM 调查器（LLM Investigator）** — [`15-llm-investigator.md`](../../interview/15-llm-investigator.md) · 状态：**M3B 已实现（Implemented in M3B）**
  LLM 只承担一个变换：把有界 Evidence 转换为结构化调查结果；编排归工作流、观测归能力端口、授权归策略与 HITL。Provider、模型、超时、重试与变更类动作置信度阈值均为运维配置，真实 provider 失败会被显式记录，绝不静默回退到确定性行为。

## 结构化输出

- **结构化输出（Structured Output）** — [`01-structured-output.md`](../../interview/01-structured-output.md) · 状态：**已实现（Implemented）**
  把模型意图转换为经 schema 校验的结构化数据，而非可执行文本；`backend/app/domain/actions/models.py` 定义严格的 Pydantic 动作模型，策略与适配器只接收可拒绝未知字段的有类型输入。

- **结构化输出 · provider API（Structured Output provider API）** — [`16-structured-output.md`](../../interview/16-structured-output.md) · 状态：**M3B 已实现（Implemented in M3B）**
  核心 provider API 返回 `InvestigationModelOutput` 而非任意文本；Pydantic v2 约束文本、置信度、引用数量与 `ActionType` 枚举并禁止额外字段，没有地方返回审批、命令、凭据、PromQL/LogQL 或工具调用。存储的是简短可审计的决策摘要，而非隐藏的思维链。

## 提示注入（Prompt Injection）

- **提示注入（Prompt Injection）** — [`17-prompt-injection.md`](../../interview/17-prompt-injection.md) · 状态：**M3B 已实现（Implemented in M3B）**
  日志、工单、告警与运维备注都被视为可被攻击者影响的不可信数据；v1 系统提示把所有 Evidence 标记为不可信，禁止内嵌的角色声明、命令与指令覆盖。提示只是纵深防御，可强制执行的控制在生成之后：严格 schema、Incident 内 Evidence ID 校验、确定性策略与审批；对抗性夹具覆盖指令覆盖、伪造 ID、不支持动作与注入授权字段等。

## 评估（Evaluation）

- **评估（Evaluation）** — [`07-evaluation.md`](../../interview/07-evaluation.md) · 状态：**M3B 建立基础；更全面的评估计划中（Foundation in M3B）**
  目前已有确定性的动作安全测试；M3B 增加了 `InvestigationEvalCase` 夹具、安全用例与指标（Evidence Precision/Recall、Action Accuracy、Grounding Validity 等）。完整的 Incident 数据集与大规模模型评估计划在后续里程碑落地。

- **Agent 评估（Agent Evaluation）** — [`18-agent-evaluation.md`](../../interview/18-agent-evaluation.md) · 状态：**M3B 已实现（Implemented in M3B）**
  引入可复用的 `InvestigationEvalCase` 夹具，报告 Evidence Precision/Recall、Action Accuracy、Grounding Validity、Unsupported Action Rate 等指标；同一批用例可跑确定性逻辑、fake provider 与可选的真实模型评估，CI 不依赖 API key。安全用例是一等评估对象——编造证据、提出不支持动作或注入授权的高质量叙事依然判失败。

## Ansible / 执行安全

- **执行器与 Ansible（Executor and Ansible）** — [`06-executor-and-ansible.md`](../../interview/06-executor-and-ansible.md) · 状态：**已实现（Implemented）**
  执行器端口把领域动作与基础设施传输隔离（`ActionExecutor`、`MockActionExecutor`、`AnsibleActionExecutor` 与固定 Playbook）；领域层不接触 SSH、子进程语法、inventory 路径或 Ansible 内部细节。

- **可移植执行边界（Portable Execution Boundary）** — [`08-portable-execution-boundary.md`](../../interview/08-portable-execution-boundary.md) · 状态：**M1B 已实现（Implemented in M1B）**
  严格的 `ActionRequest` 让 Policy 能对传给适配器的确切对象授权，Agent 无法通过 API 走私命令语法、inventory、playbook 路径或传输凭据；目标归属、动作类别与审批状态等授权事实由确定性规则判定，风险 Agent 只能补充建议，不能推翻 deny。
