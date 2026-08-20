# LLM 调查器（LLM Investigator）

[English](../../design/llm-investigator.md) | [简体中文](llm-investigator.md)

M3B 增加一项范围狭窄的 AI 能力：把有界、持久的 Incident Evidence 转换为经过校验的 `InvestigationResult`（调查结果）。它不是聊天机器人，也不是执行型 Agent。

```text
Capabilities -> durable Evidence -> EvidenceContextBuilder -> LLMIncidentInvestigator
             -> strict InvestigationModelOutput -> InvestigationGuard -> action proposal
             -> ActionPolicyEngine -> approval/execution boundary
```

`IncidentInvestigator` 仍是工作流端口（Port）。`DeterministicInvestigator` 是离线与 CI 环境下的基线；`LLMIncidentInvestigator` 依赖 `StructuredReasoningProvider`。生产模式是运维人员的显式选择，Provider 故障绝不会静默切换模式。

v1 提示词只发送摘要、有界摘录、安全元数据与 Evidence ID。选择逻辑是确定性的：优先健康/告警/指标，保持来源多样性，并强制条数与字符预算。Evidence 被明确标记为不可信：日志、工单与运维人员文本不能发出指令。提示词与原始 Provider 响应不会被持久化。

严格 Schema 禁止多余字段，且不暴露命令、查询语言、执行器（executor）、凭据、风险覆盖（risk override）、审批或工具调用字段。Evidence 引用必须唯一、必须来自当前 Incident 上下文，并且在给出 Diagnosis（诊断）或动作时非空。不支持的 `ActionType` 值、低置信度的变更类提议（mutating proposal），以及前后不一致的“证据不足”输出，都会安全失败（fail closed）。

只有可审计的结论会被保留：陈述（statement）、根因（root cause）、决策摘要、置信度、不确定性、Evidence 引用、Provider/模型/提示词版本、延迟，以及可选的 token 计数。私有的思维链（chain-of-thought）、原始提示词、鉴权头与原始 Evidence 正文均被排除。

第一个适配器使用 OpenAI Responses API，启用严格 JSON Schema、`store=false`、固定的运维自有端点、无工具、有界响应，并提供类型化的超时/限流/格式错误处理。参见[官方 Responses API 参考](https://platform.openai.com/docs/api-reference/responses)。

M3B 不引入持久化 HITL、RAG、MCP、任意工具调用或自主修复（autonomous remediation）。
