# 可观测性能力（Observability Capabilities）

[English](../../design/observability-capabilities.md) | [简体中文](observability-capabilities.md)

## 范围（Scope）

M3A 让 Incident Workflow（事故工作流）能够主动收集有界、只读的 Evidence（证据），而不引入 LLM、RAG、MCP、持久化 HITL（Human-in-the-loop，人在回路）、任意查询语言或 Incident Lab（事故实验室）。依赖方向是 `Workflow -> Capability Port <- Adapter`；Domain（领域层）不依赖 LangGraph、HTTPX、Prometheus、Loki、工单厂商或 MCP 中的任何一项。

## 类型化查询（Typed queries）

`MetricQuery` 表达稳定的 `MetricKind`（指标种类）、服务、环境、有界时间窗口、步长（step）与聚合方式。`PrometheusMetricsAdapter` 独占全部 PromQL 模板，并支持官方的 `/api/v1/query` 与 `/api/v1/query_range` 响应格式（response envelope）。任何 API 或 Agent 字段都不接受裸 PromQL。

`LogQuery` 表达服务、环境、严重级别、字面关键字、时间范围与条数上限（limit）。`LokiLogsAdapter` 独占发送到 `/loki/api/v1/query_range` 的流选择器（stream selector）与字面过滤器。租户与鉴权请求头只来自运维配置。这里使用的端点与有界参数由官方 API 定义：[Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/) 与 [Loki HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/)。

`TicketQuery` 与厂商无关（vendor-neutral）。M3A 提供一个确定性的、由固定 fixture 支撑的 Mock 适配器；Jira、GitHub Issues 或 ServiceNow 适配器之后可以实现同一个 Port（端口），无需改动工作流状态。`HealthCapability` 呈现调查语义（`get_service_health`），即使其适配器复用了受控的只读 Action 边界。

## 查询安全（Query safety）

`CapabilityQueryPolicy` 拒绝未知服务、过大的时间范围、过小的指标步长、被禁止的指标种类、超量的序列（series）、过大的日志/工单条数上限以及不安全的关键字。服务与环境选择器必须是严格标识符。查询对象不暴露 URL、租户、请求头或任意标签。只读意味着没有变更权限，但并不意味着可以无限消耗资源。

共享 HTTP 客户端统一应用超时、连接数限制、状态校验、JSON 校验与响应字节数上限。错误会被映射为安全的 Capability（能力）失败，且不携带鉴权头、Cookie、租户机密、响应体或已配置的 URL。

## 证据与来源追溯（Evidence and provenance）

适配器的观测结果会被归一化为既有的 Incident Evidence：

- Prometheus -> `METRIC`
- Loki -> `LOG`
- Ticket -> `TICKET`
- Health -> `SERVICE_STATUS`

Evidence 保留来源、不透明的来源引用（opaque source reference）、观测时间与采集时间、采集器（collector）、有界的摘要/摘录、筛选后的安全元数据以及 M1C 指纹。原始指标响应与大体积日志正文永远不会进入 Incident 数据库或 Graph State（图状态）。稳定的工作流采集窗口与不透明引用，使节点重放可以通过既有的 Incident 指纹去重。

## 工作流与故障处理（Workflow and failure handling）

Worker 启动时根据启用的 Services 与运维配置构建 `IncidentCapabilities`，并注入 `WorkflowService`。`collect_context` 以每个 Capability 各自的超时并发收集已配置的来源。结果按指标/日志/工单/健康的确定性顺序被消费。单个来源失败会记录一条安全的降级审计事件，并保留其他 Evidence。LangGraph 状态只接收最终产生的 Evidence ID。

M3A 在部分或全部外部来源不可用时有意识地降级；确定性调查器仍可使用既有的 Incident Evidence。自动化的最低证据策略（minimum-evidence policy）会推迟到其运维语义定义清楚之后再实施。
