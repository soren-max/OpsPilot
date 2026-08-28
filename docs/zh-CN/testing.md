# 测试策略（Testing Strategy）

M8.5 测试覆盖严格部署配置、双控制模式、command injection、未知/跨环境 Profile、缺失凭据、
secret-safe preview、迁移就绪度、Ticket/API 兼容边界与架构约束。独立 `legacy-ssh-e2e` CI Job
使用 synthetic SSH host 和运行时生成的临时密钥，验证真实 Ansible-over-SSH 与恢复后验证。

M8 测试覆盖 deterministic routing、profile allowlist、outbox 幂等与 lease、worker crash、
UNKNOWN recovery、Harness contract/status mapping、reconciliation、独立 verification、OTel、API
与前端。默认 CI 不需要真实 Harness SaaS。

[English](../testing.md) | [简体中文](testing.md)

## 单元测试

领域模型测试拒绝未知动作、不匹配的参数模式、不安全的标识符与多余字段。表驱动（table-driven）的策略测试覆盖只读、中等风险、审批（Approval）与 Target 规则。

## 集成测试

适配器（Adapter）测试验证固定的 Action-to-Playbook 映射、生成的变量、白名单与动作后验证（post-action verification）。现有的 API、数据库、审批与前端测试保护已弃用的迁移基线（deprecated migration baseline）。

## 工作流测试

M2 测试覆盖图拓扑、JSON 状态、节点路由、确定性的成功/阻塞/等待/失败路径、幂等重放、WorkflowRun 持久化、审计轨迹、RBAC API 行为与迁移往返（migration round trips）。运行时集成测试证明：配置的 Mock 与 Ansible 适配器会被调用，启用的 Target 白名单与确定性策略仍然把关（gate）执行，缺失 `ActionService` 时默认关闭（fail closed），`WAITING_APPROVAL` 永远不会调用会变更状态的适配器，且执行节点重试不会重复派发同一个动作。架构测试防止 Domain 到 LangGraph 或 executor 实现的导入、节点中直接使用 Ansible/SQLAlchemy，以及工作流运行时中隐式导入 Mock。M4 将增加针对持久化检查点器的持久审批中断/恢复测试。

M3A 增加表驱动的查询策略测试；受控的 MetricKind-to-PromQL 与 LogQuery-to-LogQL 映射测试；有界响应、超时、溯源（provenance）、部分失败与活跃采集（active collection）测试。M3B 增加严格模式、证据锚定（evidence grounding）、提示注入（prompt-injection）、Provider 失败/重试、评估夹具（evaluation fixture）与工作流授权边界测试。默认 CI 保持确定性并使用模拟的 HTTP 传输；可选的真实 Provider 测试需要显式的本地选择加入（opt-in）与凭据。

## 安全测试

当前套件覆盖模式拒绝、策略默认关闭行为、输出脱敏（redaction）、固定的 Ansible 映射，以及具有代表性的不安全进程终止（process-kill）请求。CI 还会运行启发式机密扫描与前端依赖审计。

未来的里程碑将增加事故数据集（incident datasets）、Agent 评估、对抗性安全评估与轨迹断言（trace assertions）。
