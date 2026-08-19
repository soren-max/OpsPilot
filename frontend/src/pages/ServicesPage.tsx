import { useQuery } from "@tanstack/react-query";
import { RotateCw, SearchCheck, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { auditsApi, catalogApi, tasksApi } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import {
  DataTable,
  CapabilityReason,
  DetailDrawer,
  EnvironmentBadge,
  FilterBar,
  InlineNotice,
  PageHeader,
  PermissionGate,
  SearchInput,
  PageSection,
  StatusBadge,
  TablePagination,
  ToolbarActions,
} from "../components/OpsUI";
import type { Service } from "../types";
import type { OperationCapabilities } from "../services/operationCapabilities";
import { queryKeys } from "../query/queryKeys";

const PAGE_SIZE = 15;

export function ServicesPage({
  environmentId,
  environmentName,
  environmentLevel,
  capabilities,
}: {
  environmentId: string;
  environmentName: string;
  environmentLevel: "DEVELOPMENT" | "TEST" | "PRODUCTION";
  capabilities: OperationCapabilities;
}) {
  const { status: statusCapability, restart: restartCapability } = capabilities;
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<Service | null>(null);
  const search = params.get("search") ?? "";
  const host = params.get("host") ?? "ALL";
  const status = params.get("status") ?? "ALL";
  const order = params.get("order") ?? "exception";
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const services = useQuery({
    queryKey: queryKeys.services(environmentId),
    queryFn: () => catalogApi.services(environmentId),
  });
  const hosts = useQuery({
    queryKey: queryKeys.hosts(environmentId),
    queryFn: () => catalogApi.hosts(environmentId),
  });
  const hostServices = useQuery({
    queryKey: queryKeys.hostServices(host === "ALL" ? "" : host),
    queryFn: () => catalogApi.hostServices(host),
    enabled: host !== "ALL",
  });
  const snapshots = useQuery({
    queryKey: queryKeys.statusSnapshots(environmentId),
    queryFn: () => tasksApi.statusSnapshots(environmentId),
  });
  const lastCheckByService = useMemo(() => {
    const latest = new Map<string, string>();
    for (const snapshot of snapshots.data ?? []) {
      const current = latest.get(snapshot.service_id);
      if (!current || Date.parse(snapshot.observed_at) > Date.parse(current)) {
        latest.set(snapshot.service_id, snapshot.observed_at);
      }
    }
    return latest;
  }, [snapshots.data]);
  useEffect(() => {
    setSelected(null);
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete("host");
        next.delete("page");
        return next;
      },
      { replace: true },
    );
  }, [environmentId, setParams]);
  const setParam = (key: string, value: string) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (!value || value === "ALL" || (key === "page" && value === "1")) next.delete(key);
      else next.set(key, value);
      if (key !== "page") next.delete("page");
      return next;
    });
  const filtered = useMemo(() => {
    const hostServiceIds = new Set(hostServices.data?.map((service) => service.id));
    const result = (services.data ?? []).filter((item) => {
      const statusMatch =
        status === "ALL" ||
        (status === "EXCEPTION"
          ? item.current_status !== "RUNNING"
          : item.current_status === status);
      return (
        (host === "ALL" || hostServiceIds.has(item.id)) &&
        statusMatch &&
        `${item.name} ${item.service_type} ${item.description ?? ""}`
          .toLowerCase()
          .includes(search.toLowerCase())
      );
    });
    const severity: Record<string, number> = {
      UNAVAILABLE: 0,
      DEGRADED: 1,
      UNKNOWN: 2,
      RUNNING: 3,
    };
    return result.sort((a, b) =>
      order === "name"
        ? a.name.localeCompare(b.name)
        : (severity[a.current_status] ?? 9) - (severity[b.current_status] ?? 9),
    );
  }, [host, hostServices.data, services.data, search, status, order]);
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const clearFilters = () => setParams({});

  return (
    <div className="page-stack data-page services-page">
      <PageHeader
        title="服务管理"
        description="以异常优先顺序查看服务资产、部署环境与关联主机，并下钻最近任务和操作记录。"
        actions={
          <ToolbarActions>
            <PermissionGate capability={statusCapability} blockedLabel="状态检查">
              <Link className="button button--primary" to="/#quick-status-check">
                <SearchCheck size={16} /> 状态检查
              </Link>
            </PermissionGate>
            <PermissionGate capability={restartCapability} blockedLabel="重启">
              <Link className="button button--secondary" to="/?action=restart#quick-status-check">
                <RotateCw size={16} /> 重启{restartCapability.requiresApproval ? " · 需审批" : ""}
              </Link>
            </PermissionGate>
          </ToolbarActions>
        }
      />
      <PageSection
        title="服务清单"
        description={`${services.data?.length ?? 0} 个服务已纳入 ${environmentName}`}
        className="operations-table-card"
      >
        <FilterBar>
          <span className="filter-context" title="环境由顶部全局选择器控制">
            环境：{environmentName}
          </span>
          <SearchInput
            value={search}
            onChange={(value) => setParam("search", value)}
            placeholder="搜索服务名称、模块或描述"
            ariaLabel="搜索服务"
          />
          <select
            value={host}
            onChange={(event) => setParam("host", event.target.value)}
            aria-label="按主机筛选服务"
            disabled={hosts.isLoading || Boolean(hosts.error)}
          >
            <option value="ALL">全部主机</option>
            {(hosts.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={(event) => setParam("status", event.target.value)}
            aria-label="按状态筛选"
          >
            <option value="ALL">全部状态</option>
            <option value="EXCEPTION">仅看异常</option>
            <option value="RUNNING">运行正常</option>
            <option value="DEGRADED">降级</option>
            <option value="UNAVAILABLE">不可用</option>
            <option value="UNKNOWN">未知</option>
          </select>
          <select
            value={order}
            onChange={(event) => setParam("order", event.target.value)}
            aria-label="服务排序"
          >
            <option value="exception">异常优先</option>
            <option value="name">名称排序</option>
          </select>
          <span className="filter-bar__count">{filtered.length} 条记录</span>
        </FilterBar>
        <div id="services-write-policy" className="operation-policy-strip" role="note">
          <strong>后端有效操作能力</strong>
          <CapabilityReason capability={statusCapability} />
          <CapabilityReason capability={restartCapability} />
        </div>
        {services.isLoading || (host !== "ALL" && hostServices.isLoading) ? (
          <LoadingState variant="table" />
        ) : services.error || (host !== "ALL" && hostServices.error) ? (
          <ErrorState
            error={(services.error ?? hostServices.error)!}
            onRetry={() => {
              void services.refetch();
              if (host !== "ALL") void hostServices.refetch();
            }}
          />
        ) : !filtered.length ? (
          <EmptyState
            title={services.data?.length ? "没有匹配结果" : "暂无服务资产"}
            message={services.data?.length ? "请调整搜索词或筛选条件。" : "当前环境尚未登记服务。"}
            action={
              services.data?.length ? (
                <button className="button button--secondary" onClick={clearFilters}>
                  清除筛选
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            {snapshots.error && (
              <InlineNotice title="Status snapshot 暂不可用" tone="warning">
                最近检查时间显示为“未记录”。
              </InlineNotice>
            )}
            <DataTable ariaLabel="服务列表">
              <thead>
                <tr>
                  <th>服务名称</th>
                  <th>模块</th>
                  <th>运行状态</th>
                  <th>部署环境</th>
                  <th>关联主机</th>
                  <th>最近检查</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {visible.map((service) => (
                  <tr key={service.id}>
                    <td>
                      <span className="entity-cell">
                        <Wrench size={16} aria-hidden="true" />
                        <span>
                          <strong>{service.name}</strong>
                          <small>{service.description ?? "未填写服务描述"}</small>
                        </span>
                      </span>
                    </td>
                    <td>
                      <span className="type-tag">{service.service_type}</span>
                      {service.is_middleware && <small>中间件</small>}
                    </td>
                    <td>
                      <StatusBadge status={service.current_status} domain="service" />
                    </td>
                    <td>
                      <EnvironmentBadge name={environmentName} level={environmentLevel} />
                    </td>
                    <td className="number-cell">{service.host_count}</td>
                    <td>
                      {lastCheckByService.has(service.id) ? (
                        formatDate(lastCheckByService.get(service.id)!)
                      ) : (
                        <span className="unrecorded-value" title="尚无 status snapshot">
                          未记录
                        </span>
                      )}
                    </td>
                    <td>
                      <div className="table-row-actions" aria-label={`${service.name} 操作`}>
                        <PermissionGate
                          capability={statusCapability}
                          blockedLabel="status"
                          showReason={false}
                          className="row-action"
                        >
                          <Link
                            className="row-action"
                            to={`/?action=status&service=${service.id}#quick-status-check`}
                          >
                            status
                          </Link>
                        </PermissionGate>
                        <PermissionGate
                          capability={restartCapability}
                          blockedLabel="restart"
                          showReason={false}
                          className="row-action"
                        >
                          <Link to={`/?action=restart&service=${service.id}#quick-status-check`}>
                            restart
                          </Link>
                        </PermissionGate>
                        <button className="row-action" onClick={() => setSelected(service)}>
                          详情
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            <TablePagination
              page={page}
              pageSize={PAGE_SIZE}
              total={filtered.length}
              onPageChange={(value) => setParam("page", String(value))}
            />
          </>
        )}
      </PageSection>
      <ServiceDrawer
        service={selected}
        environmentName={environmentName}
        capabilities={capabilities}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function ServiceDrawer({
  service,
  environmentName,
  capabilities,
  onClose,
}: {
  service: Service | null;
  environmentName: string;
  capabilities: OperationCapabilities;
  onClose: () => void;
}) {
  const hosts = useQuery({
    queryKey: queryKeys.serviceHosts(service?.id ?? ""),
    queryFn: () => catalogApi.serviceHosts(service!.id),
    enabled: Boolean(service),
  });
  const tasks = useQuery({
    queryKey: queryKeys.tasks,
    queryFn: tasksApi.list,
    enabled: Boolean(service),
  });
  const audits = useQuery({
    queryKey: queryKeys.audits,
    queryFn: auditsApi.list,
    enabled: Boolean(service),
  });
  const relatedTasks =
    tasks.data
      ?.filter((task) => task.targets.some((target) => target.service_id === service?.id))
      .slice(0, 5) ?? [];
  const relatedIds = new Set(relatedTasks.map((task) => task.id));
  const relatedAudits =
    audits.data?.filter((audit) => audit.task_id && relatedIds.has(audit.task_id)).slice(0, 5) ??
    [];
  return (
    <DetailDrawer
      open={Boolean(service)}
      title={service?.name ?? "服务详情"}
      subtitle={service ? `${service.service_type} · ${service.id}` : undefined}
      onClose={onClose}
    >
      {service && (
        <div className="drawer-sections">
          <section>
            <h3>服务信息</h3>
            <dl className="key-value">
              <div>
                <dt>当前状态</dt>
                <dd>
                  <StatusBadge status={service.current_status} domain="service" />
                </dd>
              </div>
              <div>
                <dt>部署环境</dt>
                <dd>{environmentName}</dd>
              </div>
              <div>
                <dt>关联主机</dt>
                <dd>{service.host_count}</dd>
              </div>
              <div>
                <dt>服务模块</dt>
                <dd>{service.service_type}</dd>
              </div>
            </dl>
          </section>
          <section>
            <h3>部署主机</h3>
            {hosts.isLoading ? (
              <LoadingState label="加载主机关系" />
            ) : hosts.error ? (
              <ErrorState error={hosts.error} onRetry={() => void hosts.refetch()} />
            ) : hosts.data?.length ? (
              <ul className="resource-list">
                {hosts.data.map((host) => (
                  <li key={host.id}>
                    <span className="mono">{host.name}</span>
                    <StatusBadge status={host.last_status} domain="host" compact />
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="无部署主机" message="该服务尚未关联主机。" />
            )}
          </section>
          <section>
            <h3>最近任务与执行历史</h3>
            {tasks.error ? (
              <ErrorState error={tasks.error} onRetry={() => void tasks.refetch()} />
            ) : relatedTasks.length ? (
              <ul className="mini-task-list">
                {relatedTasks.map((task) => (
                  <li key={task.id}>
                    <Link className="mono entity-link" to={`/tasks?task=${task.id}`}>
                      {task.id.slice(0, 8)}
                    </Link>
                    <span>{task.action}</span>
                    <StatusBadge status={task.status} domain="task" compact />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-copy">暂无相关任务。</p>
            )}
          </section>
          <section>
            <h3>操作记录</h3>
            {audits.error ? (
              <ErrorState error={audits.error} onRetry={() => void audits.refetch()} />
            ) : relatedAudits.length ? (
              <ul className="audit-compact-list">
                {relatedAudits.map((audit) => (
                  <li key={audit.id}>
                    <strong>{audit.actor}</strong>
                    <span>{audit.message}</span>
                    <small>{formatDate(audit.created_at)}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-copy">暂无相关审计记录。</p>
            )}
          </section>
          <section className="drawer-action-group">
            <h3>受控操作</h3>
            <PermissionGate capability={capabilities.status} blockedLabel="状态检查">
              <Link className="button button--primary" to="/#quick-status-check">
                <SearchCheck size={16} /> 状态检查
              </Link>
            </PermissionGate>
            <PermissionGate capability={capabilities.restart} blockedLabel="重启">
              <Link
                className="button button--secondary"
                to={`/?action=restart&service=${service.id}#quick-status-check`}
              >
                <RotateCw size={15} /> 重启
                {capabilities.restart.requiresApproval ? " · 需审批" : ""}
              </Link>
            </PermissionGate>
            <div className="operation-policy-note" role="note">
              <strong>后端有效操作能力</strong>
              <CapabilityReason capability={capabilities.status} />
              <CapabilityReason capability={capabilities.restart} />
            </div>
          </section>
        </div>
      )}
    </DetailDrawer>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(
    new Date(value),
  );
}
