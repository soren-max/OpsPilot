import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  HardDrive,
  PlayCircle,
  SearchCheck,
  Server,
  ShieldAlert,
  Siren,
  Workflow,
} from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { approvalsApi, auditsApi, catalogApi, incidentsApi, systemApi, tasksApi } from "../api";
import { StatusCheckComposer } from "../components/dashboard/StatusCheckComposer";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import {
  CapabilityReason,
  DataTable,
  InlineNotice,
  PageHeader,
  PageSection,
  StatusBadge,
} from "../components/OpsUI";
import { queryKeys } from "../query/queryKeys";
import { mapHostsToAssets } from "../services/assetService";
import { buildDashboardViewModel } from "../services/dashboardService";
import type { OperationCapabilities } from "../services/operationCapabilities";
import type { Audit, SecurityContext, SystemReady, Task } from "../types";

export function DashboardPage({
  environmentId,
  environmentName,
  environmentCode,
  environmentLevel,
  security,
  readiness,
  readinessError,
  capabilities,
}: {
  environmentId: string;
  environmentName: string;
  environmentCode: string;
  environmentLevel: "DEVELOPMENT" | "TEST" | "PRODUCTION";
  security: SecurityContext;
  readiness?: SystemReady;
  readinessError: unknown;
  capabilities: OperationCapabilities;
}) {
  const health = useQuery({
    queryKey: queryKeys.system.health,
    queryFn: systemApi.health,
    refetchInterval: 15_000,
  });
  const services = useQuery({
    queryKey: queryKeys.services(environmentId),
    queryFn: () => catalogApi.services(environmentId),
  });
  const hosts = useQuery({
    queryKey: queryKeys.hosts(environmentId),
    queryFn: () => catalogApi.hosts(environmentId),
  });
  const tasks = useQuery({
    queryKey: queryKeys.tasks,
    queryFn: tasksApi.list,
    refetchInterval: 5_000,
  });
  const audits = useQuery({
    queryKey: queryKeys.audits,
    queryFn: auditsApi.list,
    refetchInterval: 10_000,
  });
  const snapshots = useQuery({
    queryKey: queryKeys.statusSnapshots(environmentId),
    queryFn: () => tasksApi.statusSnapshots(environmentId),
    refetchInterval: 10_000,
  });
  const incidents = useQuery({
    queryKey: queryKeys.incidents(environmentCode),
    queryFn: () => incidentsApi.list(environmentCode),
    refetchInterval: 10_000,
  });
  const approvals = useQuery({
    queryKey: queryKeys.approvals,
    queryFn: () => approvalsApi.list(),
    refetchInterval: 10_000,
  });
  const executions = useQuery({
    queryKey: queryKeys.executions,
    queryFn: () => incidentsApi.executions(),
    refetchInterval: 5_000,
  });
  const environmentTasks = useMemo(
    () => (tasks.data ?? []).filter((item) => item.environment_id === environmentId),
    [environmentId, tasks.data],
  );
  const environmentAudits = useMemo(() => {
    const taskIds = new Set(environmentTasks.map((item) => item.id));
    return (audits.data ?? []).filter((item) => item.task_id && taskIds.has(item.task_id));
  }, [audits.data, environmentTasks]);
  const assets = useMemo(
    () => mapHostsToAssets(hosts.data ?? [], security.environment, snapshots.data ?? []),
    [hosts.data, security.environment, snapshots.data],
  );
  const dashboard = useMemo(
    () =>
      buildDashboardViewModel({
        assets,
        services: services.data ?? [],
        tasks: environmentTasks,
        audits: environmentAudits,
        snapshots: snapshots.data ?? [],
        health: health.data,
      }),
    [assets, environmentAudits, environmentTasks, health.data, services.data, snapshots.data],
  );
  const primaryLoading = services.isLoading || hosts.isLoading || tasks.isLoading;
  const primaryError = services.error ?? hosts.error ?? tasks.error;
  const recentAudits = [...environmentAudits]
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    .slice(0, 5);
  const environmentIncidents = incidents.data?.items ?? [];
  const environmentIncidentIds = new Set(environmentIncidents.map((item) => item.id));
  const activeIncidents = environmentIncidents
    .filter((item) => !["RESOLVED", "CLOSED"].includes(item.status))
    .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at));
  const waitingApprovals = (approvals.data ?? []).filter(
    (item) => item.status === "PENDING" && environmentIncidentIds.has(item.incident_id),
  );
  const environmentExecutions = (executions.data ?? []).filter((item) =>
    environmentIncidentIds.has(item.incident_id),
  );
  const runningExecutions = environmentExecutions.filter((item) => item.status === "RUNNING");
  const failedVerifications = environmentExecutions.filter(
    (item) => item.verification_status === "FAILED",
  );
  const resolvedIncidents = environmentIncidents.filter((item) =>
    ["RESOLVED", "CLOSED"].includes(item.status),
  );
  return (
    <div className="page-stack dashboard-page dashboard-operations">
      <PageHeader
        title="运维总览"
        description="当前环境的系统就绪度、服务状态、任务与安全策略总览。"
        actions={
          <span className="page-header__status">
            <Activity size={15} aria-hidden="true" /> 核心数据每 5–15 秒刷新
          </span>
        }
      />

      <div className="dashboard-top-grid">
        <PageSection
          className="dashboard-system-panel"
          title="系统状态"
          description="来自健康检查、就绪检查与公开安全上下文；缺失数据不会推断为正常"
        >
          <div className="system-status-strip">
            <SystemStatusItem
              id="api"
              label="API"
              status={health.data?.status.toUpperCase() ?? "UNKNOWN"}
              detail={health.data ? "健康检查已响应" : "尚未检查"}
            />
            <SystemStatusItem
              id="application"
              label="Application"
              status={readiness?.application.toUpperCase() ?? "UNKNOWN"}
              detail="应用编排层"
            />
            <SystemStatusItem
              id="readiness"
              label="Readiness"
              status={readiness?.status.toUpperCase() ?? "UNKNOWN"}
              detail={readiness ? `数据库 ${readiness.database}` : "尚未检查"}
            />
            <SystemStatusItem
              id="environment"
              label="Environment level"
              status={environmentLevel}
              detail={environmentName || "未提供"}
            />
            <SystemStatusItem
              id="execution-backend"
              label="Execution Backend"
              status={readiness?.execution_backend.available ? "AVAILABLE" : "UNAVAILABLE"}
              detail={readiness?.execution_backend.backend ?? security.executor ?? "未提供"}
            />
            <SystemStatusItem
              id="action-boundary"
              label="Action Boundary"
              status="STRUCTURED"
              detail="Policy → Approval → Execute → Verify"
            />
            <SystemStatusItem
              id="write-policy"
              label="Write policy"
              status={security.write_operations ? "AVAILABLE" : "DISABLED"}
              detail={security.write_operations ? "写操作总开关已启用" : "写操作总开关关闭"}
            />
            <SystemStatusItem
              id="production-policy"
              label="Production policy"
              status={security.production_operations ? "AVAILABLE" : "DISABLED"}
              detail={security.production_operations ? "生产写操作已启用" : "生产写操作默认禁止"}
            />
          </div>
          {Boolean(readinessError) && (
            <InlineNotice title="Readiness 暂不可用" tone="warning">
              就绪接口暂不可用，Worker、Readiness 与 Command profile 显示为“尚未检查”。
            </InlineNotice>
          )}
        </PageSection>
        <section className="operation-capability-summary" aria-label="当前操作能力">
          <CapabilityReason capability={capabilities.status} />
          <CapabilityReason capability={capabilities.restart} />
        </section>
      </div>

      <section className="operational-signal-strip" aria-label="Operational incident signals">
        <OperationalKpi
          label="Open Incidents"
          value={incidents.isLoading ? "—" : activeIncidents.length}
          detail="Requires operator awareness"
          to="/incidents"
          tone={activeIncidents.length ? "danger" : "success"}
          icon={<Siren size={17} aria-hidden="true" />}
        />
        <OperationalKpi
          label="Waiting Approval"
          value={approvals.isLoading ? "—" : waitingApprovals.length}
          detail="Governed actions paused"
          to={
            waitingApprovals[0]
              ? `/incidents/${waitingApprovals[0].incident_id}#approval`
              : "/incidents"
          }
          tone={waitingApprovals.length ? "warning" : "neutral"}
          icon={<ShieldAlert size={17} aria-hidden="true" />}
        />
        <OperationalKpi
          label="Running Execution"
          value={executions.isLoading ? "—" : runningExecutions.length}
          detail="Provider work in progress"
          to="/tasks"
          tone={runningExecutions.length ? "info" : "neutral"}
          icon={<PlayCircle size={17} aria-hidden="true" />}
        />
        <OperationalKpi
          label="Failed Verification"
          value={executions.isLoading ? "—" : failedVerifications.length}
          detail="Execution and health diverged"
          to={
            failedVerifications[0]
              ? `/incidents/${failedVerifications[0].incident_id}#execution`
              : "/incidents"
          }
          tone={failedVerifications.length ? "danger" : "neutral"}
          icon={<AlertTriangle size={17} aria-hidden="true" />}
        />
        <OperationalKpi
          label="Recent Resolved"
          value={incidents.isLoading ? "—" : resolvedIncidents.length}
          detail="Current incident result set"
          to="/incidents"
          tone="success"
          icon={<CheckCircle2 size={17} aria-hidden="true" />}
        />
      </section>
      {incidents.error || approvals.error || executions.error ? (
        <InlineNotice title="Some incident signals are unavailable" tone="warning">
          Unknown data is not counted as healthy. Open the related page to retry its data source.
        </InlineNotice>
      ) : null}

      {primaryLoading ? (
        <LoadingState variant="cards" label="正在汇总运行数据" />
      ) : primaryError ? (
        <ErrorState
          error={primaryError}
          onRetry={() => {
            void services.refetch();
            void hosts.refetch();
            void tasks.refetch();
          }}
        />
      ) : (
        <section className="operations-kpi-strip" aria-label="资产与服务概览">
          <Kpi label="总资产" value={dashboard.assets.total} icon={<Server size={17} />} />
          <Kpi
            label="服务检查正常主机"
            value={dashboard.assets.healthy}
            tone="success"
            icon={<CheckCircle2 size={17} />}
          />
          <Kpi
            label="异常资产"
            value={dashboard.assets.abnormal}
            tone="danger"
            icon={<AlertTriangle size={17} />}
          />
          <Kpi
            label="最近检查"
            value={compactDate(dashboard.assets.lastCheckedAt)}
            icon={<Clock3 size={17} />}
          />
          <Kpi
            label="Running"
            value={dashboard.services.running}
            tone="success"
            icon={<Activity size={17} />}
          />
          <Kpi
            label="Stopped"
            value={dashboard.services.stopped}
            tone="warning"
            icon={<HardDrive size={17} />}
          />
          <Kpi label="Unknown" value={dashboard.services.unknown} icon={<Workflow size={17} />} />
        </section>
      )}

      <div className="dashboard-workbench">
        <PageSection
          className="dashboard-incident-panel"
          title="Active incidents"
          description="Updated operational incidents in the selected environment"
          actions={
            <Link className="section-link" to="/incidents">
              Open incident queue
            </Link>
          }
        >
          {incidents.isLoading ? (
            <LoadingState variant="cards" label="Loading incidents" />
          ) : incidents.error ? (
            <ErrorState error={incidents.error} onRetry={() => void incidents.refetch()} />
          ) : activeIncidents.length ? (
            <ul className="dashboard-incident-list">
              {activeIncidents.slice(0, 5).map((item) => (
                <li key={item.id}>
                  <span
                    className={`incident-priority incident-priority--${item.severity.toLowerCase()}`}
                  >
                    {item.severity}
                  </span>
                  <span>
                    <Link to={`/incidents/${item.id}`}>{item.title}</Link>
                    <small>
                      {item.service} · {item.environment} · {compactDate(item.updated_at)}
                    </small>
                  </span>
                  <StatusBadge status={item.status} domain="incident" compact />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No active incidents"
              message="Resolved incidents remain available in the incident queue."
            />
          )}
        </PageSection>
        <PageSection
          className="dashboard-task-table"
          title="最近任务"
          description="当前环境最近 6 条执行记录"
          actions={
            <Link className="section-link" to="/tasks">
              进入任务中心
            </Link>
          }
        >
          {tasks.isLoading ? (
            <LoadingState variant="table" />
          ) : tasks.error ? (
            <ErrorState error={tasks.error} onRetry={() => void tasks.refetch()} />
          ) : dashboard.recentTasks.length ? (
            <DataTable ariaLabel="最近任务">
              <thead>
                <tr>
                  <th>Task ID</th>
                  <th>操作</th>
                  <th>操作对象</th>
                  <th>发起人</th>
                  <th>状态</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.recentTasks.map((task) => (
                  <RecentTaskRow key={task.id} task={task} />
                ))}
              </tbody>
            </DataTable>
          ) : (
            <EmptyState title="暂无任务记录" message="当前环境尚未创建执行任务。" />
          )}
        </PageSection>

        <PageSection
          className="dashboard-risk-panel"
          title="风险提醒"
          description="失败、拒绝与超时事件"
          actions={
            <Link className="section-link" to="/audits">
              查看审计
            </Link>
          }
        >
          <ul className="risk-summary-list">
            {dashboard.risks.map((risk) => (
              <li key={risk.id}>
                <StatusBadge status={risk.status} domain="task" compact />
                <span>
                  <strong>{risk.label}</strong>
                  <small>{risk.description}</small>
                </span>
                <b>{risk.count}</b>
              </li>
            ))}
          </ul>
          {(health.error || readinessError || audits.error || snapshots.error) && (
            <InlineNotice title="部分辅助数据不可用" tone="warning">
              部分辅助接口不可用，未知数据未计为正常。
            </InlineNotice>
          )}
        </PageSection>

        <PageSection
          className="dashboard-audit-panel"
          title="最近审计"
          description="当前环境最近 5 条审计事件"
          actions={
            <Link className="section-link" to="/audits">
              查看全部
            </Link>
          }
        >
          {audits.isLoading ? (
            <LoadingState variant="cards" label="正在加载审计记录" />
          ) : audits.error ? (
            <ErrorState error={audits.error} onRetry={() => void audits.refetch()} />
          ) : recentAudits.length ? (
            <ul className="dashboard-audit-list">
              {recentAudits.map((audit) => (
                <RecentAuditItem key={audit.id} audit={audit} />
              ))}
            </ul>
          ) : (
            <EmptyState title="暂无审计记录" message="当前环境尚未产生审计事件。" />
          )}
        </PageSection>
      </div>

      <details id="quick-status-check" className="dashboard-operation-dock">
        <summary>
          <span>
            <SearchCheck size={17} aria-hidden="true" />
            快速状态检查
          </span>
          <span>
            {security.write_operations ? "受控操作" : "只读执行"} · {security.executor}
          </span>
        </summary>
        <StatusCheckComposer
          environmentId={environmentId}
          environmentName={environmentName}
          environmentLevel={environmentLevel}
          security={security}
          capabilities={capabilities}
        />
      </details>
    </div>
  );
}

function SystemStatusItem({
  id,
  label,
  status,
  detail,
}: {
  id: string;
  label: string;
  status: string;
  detail: string;
}) {
  const Icon =
    id === "database"
      ? Database
      : id === "executor"
        ? Workflow
        : id === "worker"
          ? HardDrive
          : Server;
  return (
    <div className="system-status-item">
      <Icon size={18} aria-hidden="true" />
      <span>
        <strong>{label}</strong>
        <small>{detail}</small>
      </span>
      <StatusBadge status={status} compact />
    </div>
  );
}

function OperationalKpi({
  label,
  value,
  detail,
  to,
  tone,
  icon,
}: {
  label: string;
  value: string | number;
  detail: string;
  to: string;
  tone: "neutral" | "success" | "warning" | "danger" | "info";
  icon: React.ReactNode;
}) {
  return (
    <Link className={`operational-signal operational-signal--${tone}`} to={to}>
      <span className="operational-signal__icon">{icon}</span>
      <span>
        <small>{label}</small>
        <strong>{value}</strong>
        <b>{detail}</b>
      </span>
    </Link>
  );
}

function Kpi({
  label,
  value,
  icon,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  return (
    <div className={`operations-kpi operations-kpi--${tone}`}>
      <span>{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function RecentTaskRow({ task }: { task: Task }) {
  const targets = task.targets
    .slice(0, 2)
    .map((target) => `${target.service_name}@${target.host_name}`)
    .join("、");
  return (
    <tr>
      <td>
        <Link className="mono entity-link" to={`/tasks?task=${task.id}`}>
          {task.id.slice(0, 8)}
        </Link>
      </td>
      <td>
        <span className="type-tag">{task.action}</span>
      </td>
      <td className="dashboard-task-target" title={targets}>
        {targets || "—"}
        {task.targets.length > 2 ? ` 等 ${task.targets.length} 个目标` : ""}
      </td>
      <td>{task.requested_by}</td>
      <td>
        <StatusBadge status={task.status} domain="task" compact />
      </td>
      <td>{compactDate(task.created_at)}</td>
    </tr>
  );
}

function RecentAuditItem({ audit }: { audit: Audit }) {
  return (
    <li>
      <Link to={`/audits?audit=${audit.id}`}>{audit.message}</Link>
      <span>{audit.actor}</span>
      <time dateTime={audit.created_at}>{compactDate(audit.created_at)}</time>
    </li>
  );
}

function compactDate(value: string | null) {
  if (!value) return "未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
