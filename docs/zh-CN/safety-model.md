# 安全模型（Safety Model）

[English](../safety-model.md) | [简体中文](safety-model.md)

## 先取证，后行动（Evidence Before Action）

动作理由是必需的，M3A/M3B 工作流在提出变更之前会收集可观测的证据。M3A 提供有界、类型化的证据收集；M3B 要求在动作提议被接受之前，grounded 诊断只能引用当前 Incident 中真实存在的 Evidence ID。

## 最小权限（Least Privilege）

只接受带有动作专属参数模式（action-specific parameter schemas）的已枚举动作。未知与多余的字段会校验失败。Ansible 适配器（Adapter）拥有自己的 inventory、playbook 根目录、动作映射与 Target 白名单。不存在任意 shell 动作。

## 人工控制（Human Control）

只读动作可以自动执行。重启服务属于中等风险，策略（Policy）会返回 `approval_required=true`；没有审批（Approval），`ActionService` 不会调用 executor。持久化、身份绑定的审批集成目前仅部分完成，将随工作流检查点功能一并完成。

## 设计上可审计（Auditable by Design）

Action、风险、结果、验证（Verification）与审计事件模型已经存在。Approval、Execution 与 Verification 事件已经进入事故审计轨迹（incident audit trail，M1C/M2）；Agent 与 Tool 事件可能在未来的里程碑中扩展。机密与原始模型推理绝不能作为审计证据存储。

> LLM 是决策助手，而不是授权权威。

## 默认关闭规则（Fail-Closed Rules）

- 未知动作：模式拒绝（schema rejection）
- 格式错误或多余的参数：模式拒绝
- 未知 Target：策略与适配器白名单禁止
- 没有审批的中等风险动作：不调用 executor
- 调用方提供的文件系统路径：不属于 ActionRequest
- 任意的 shell 或进程终止（process-kill）请求：没有可表示的 ActionType
