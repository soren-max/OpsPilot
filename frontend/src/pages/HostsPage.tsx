import { useQuery } from "@tanstack/react-query";
import { History, Server, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { auditsApi, catalogApi, tasksApi } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import {
  DataTable,
  DetailDrawer,
  EnvironmentBadge,
  FilterBar,
  InlineNotice,
  PageHeader,
  SearchInput,
  PageSection,
  StatusBadge,
  TablePagination,
} from "../components/OpsUI";
import { queryKeys } from "../query/queryKeys";
import { assetService } from "../services/assetService";
import type { Asset, Environment } from "../types";

const PAGE_SIZE = 15;

export function HostsPage({
  environmentId,
  environmentName,
  environments,
  onEnvironmentChange,
}: {
  environmentId: string;
  environmentName: string;
  environments: Environment[];
  onEnvironmentChange: (environmentId: string) => void;
}) {
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<Asset | null>(null);
  const search = params.get("search") ?? "";
  const status = params.get("status") ?? "ALL";
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const snapshots = useQuery({
    queryKey: queryKeys.statusSnapshots(environmentId),
    queryFn: () => tasksApi.statusSnapshots(environmentId),
  });
  const assets = useQuery({
    queryKey: [...queryKeys.assets(environmentId), snapshots.dataUpdatedAt],
    queryFn: () => assetService.list(environmentId, environmentName, null, snapshots.data ?? []),
  });

  useEffect(() => setSelected(null), [environmentId]);

  const setParam = (key: string, value: string) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (!value || value === "ALL" || (key === "page" && value === "1")) next.delete(key);
      else next.set(key, value);
      if (key !== "page") next.delete("page");
      return next;
    });
  const filtered = useMemo(
    () =>
      (assets.data ?? [])
        .filter(
          (asset) =>
            (status === "ALL" || asset.serviceCheckStatus === status) &&
            `${asset.name} ${asset.ip ?? ""}`.toLowerCase().includes(search.toLowerCase()),
        )
        .sort(
          (a, b) =>
            Number(a.serviceCheckStatus === "RUNNING") -
              Number(b.serviceCheckStatus === "RUNNING") || a.name.localeCompare(b.name),
        ),
    [assets.data, search, status],
  );
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const loading = assets.isLoading;
  const error = assets.error;

  return (
    <div className="page-stack data-page asset-page">
      <PageHeader
        title="主机 / 资产管理"
        description="主机连接状态与服务检查结果分开呈现；后端未提供连接状态时明确显示未提供。"
      />
      <PageSection
        title="资产清单"
        description={`${assets.data?.length ?? 0} 项资产已纳入 ${environmentName}`}
        className="operations-table-card"
      >
        <FilterBar>
          <SearchInput
            value={search}
            onChange={(value) => setParam("search", value)}
            placeholder="搜索资产名称或 IP"
            ariaLabel="搜索资产名称或 IP"
          />
          <select
            value={environmentId}
            onChange={(event) => onEnvironmentChange(event.target.value)}
            aria-label="按环境筛选"
          >
            {environments
              .filter((environment) => environment.enabled)
              .map((environment) => (
                <option key={environment.id} value={environment.id}>
                  {environment.name}
                </option>
              ))}
          </select>
          <select
            value={status}
            onChange={(event) => setParam("status", event.target.value)}
            aria-label="按服务检查状态筛选"
          >
            <option value="ALL">全部状态</option>
            <option value="RUNNING">服务检查正常</option>
            <option value="STOPPED">关联服务已停止</option>
            <option value="UNAVAILABLE">服务检查不可达</option>
            <option value="UNKNOWN">未知</option>
          </select>
          <span className="filter-bar__count">{filtered.length} 项资产</span>
        </FilterBar>
        {loading ? (
          <LoadingState variant="table" />
        ) : error ? (
          <ErrorState
            error={error}
            onRetry={() => {
              void assets.refetch();
            }}
          />
        ) : !filtered.length ? (
          <EmptyState
            title={assets.data?.length ? "没有匹配资产" : "暂无资产"}
            message={assets.data?.length ? "请调整名称、IP 或状态筛选。" : "当前环境尚未登记资产。"}
            action={
              assets.data?.length ? (
                <button className="button button--secondary" onClick={() => setParams({})}>
                  清除筛选
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            {snapshots.error && (
              <InlineNotice title="服务状态快照不可用" tone="warning">
                最近服务检查时间显示为“未提供”；不会将其推断为主机连接异常。
              </InlineNotice>
            )}
            <DataTable ariaLabel="企业资产列表">
              <thead>
                <tr>
                  <th>资产名称</th>
                  <th>IP</th>
                  <th>环境</th>
                  <th>类型</th>
                  <th>连接状态</th>
                  <th>服务检查状态</th>
                  <th>最近服务检查</th>
                  <th>服务数</th>
                  <th>异常摘要</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {visible.map((asset) => (
                  <tr key={asset.id}>
                    <td>
                      <span className="entity-cell entity-cell--compact">
                        <Server size={15} aria-hidden="true" />
                        <span>
                          <strong className="mono">{asset.name}</strong>
                          <small>{asset.id.slice(0, 8)}</small>
                        </span>
                      </span>
                    </td>
                    <td className="mono">{valueOrUnrecorded(asset.ip, "IP")}</td>
                    <td>
                      <EnvironmentBadge
                        name={asset.environmentName}
                        level={
                          environments.find((item) => item.id === asset.environmentId)
                            ?.environment_level
                        }
                      />
                    </td>
                    <td>{valueOrUnrecorded(asset.type, "资产类型")}</td>
                    <td>
                      {asset.connectionStatus ? (
                        <StatusBadge status={asset.connectionStatus} domain="host" />
                      ) : (
                        missing("主机连接状态")
                      )}
                    </td>
                    <td>
                      <StatusBadge status={asset.serviceCheckStatus} domain="service" />
                    </td>
                    <td>
                      {asset.lastServiceCheckAt
                        ? formatDate(asset.lastServiceCheckAt)
                        : missing("服务检查时间")}
                    </td>
                    <td className="number-cell">{asset.serviceCount}</td>
                    <td>
                      {asset.serviceCheckStatus === "RUNNING" ? (
                        <span className="muted-value">未发现状态异常</span>
                      ) : asset.serviceCheckStatus === "UNKNOWN" ? (
                        <span className="unrecorded-value">尚未检查</span>
                      ) : (
                        <span className="danger-text">
                          {hostAnomalyLabel(asset.serviceCheckStatus)}
                        </span>
                      )}
                    </td>
                    <td>
                      <button className="row-action" onClick={() => setSelected(asset)}>
                        详情
                      </button>
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
      <AssetDrawer asset={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function AssetDrawer({ asset, onClose }: { asset: Asset | null; onClose: () => void }) {
  const services = useQuery({
    queryKey: queryKeys.hostServices(asset?.id ?? ""),
    queryFn: () => catalogApi.hostServices(asset!.id),
    enabled: Boolean(asset),
  });
  const tasks = useQuery({
    queryKey: queryKeys.tasks,
    queryFn: tasksApi.list,
    enabled: Boolean(asset),
  });
  const audits = useQuery({
    queryKey: queryKeys.audits,
    queryFn: auditsApi.list,
    enabled: Boolean(asset),
  });
  const related =
    tasks.data
      ?.filter((task) => task.targets.some((target) => target.host_id === asset?.id))
      .slice(0, 5) ?? [];
  const relatedIds = new Set(related.map((task) => task.id));
  const relatedAudits =
    audits.data?.filter((item) => item.task_id && relatedIds.has(item.task_id)).slice(0, 5) ?? [];

  return (
    <DetailDrawer
      open={Boolean(asset)}
      title={asset?.name ?? "资产详情"}
      subtitle={asset ? `企业资产 · ${asset.id}` : undefined}
      onClose={onClose}
    >
      {asset && (
        <div className="drawer-sections">
          <section>
            <h3>资产信息</h3>
            <dl className="key-value">
              <div>
                <dt>IP</dt>
                <dd>{valueOrUnrecorded(asset.ip, "IP")}</dd>
              </div>
              <div>
                <dt>所属环境</dt>
                <dd>{asset.environmentName}</dd>
              </div>
              <div>
                <dt>资产类型</dt>
                <dd>{valueOrUnrecorded(asset.type, "资产类型")}</dd>
              </div>
              <div>
                <dt>主机连接状态</dt>
                <dd>
                  {asset.connectionStatus ? (
                    <StatusBadge status={asset.connectionStatus} domain="host" />
                  ) : (
                    missing("主机连接状态")
                  )}
                </dd>
              </div>
              <div>
                <dt>服务检查状态</dt>
                <dd>
                  <StatusBadge status={asset.serviceCheckStatus} domain="service" />
                </dd>
              </div>
              <div>
                <dt>最近服务检查</dt>
                <dd>
                  {asset.lastServiceCheckAt
                    ? formatDate(asset.lastServiceCheckAt)
                    : missing("服务检查时间")}
                </dd>
              </div>
              <div>
                <dt>执行方式</dt>
                <dd>{valueOrUnrecorded(asset.executorType, "Executor")}</dd>
              </div>
            </dl>
          </section>
          <section>
            <h3>关联服务</h3>
            {services.isLoading ? (
              <LoadingState label="加载服务" />
            ) : services.error ? (
              <ErrorState error={services.error} onRetry={() => void services.refetch()} />
            ) : services.data?.length ? (
              <ul className="resource-list">
                {services.data.map((service) => (
                  <li key={service.id}>
                    <span>
                      <Wrench size={15} aria-hidden="true" /> {service.name}
                    </span>
                    <StatusBadge status={service.current_status} domain="service" compact />
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="暂无关联服务" message="该资产尚未关联服务。" />
            )}
          </section>
          <section>
            <h3>最近任务</h3>
            {related.length ? (
              <ul className="mini-task-list">
                {related.map((task) => (
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
            <h3>最近审计动作</h3>
            {relatedAudits.length ? (
              <ul className="audit-compact-list">
                {relatedAudits.map((audit) => (
                  <li key={audit.id}>
                    <History size={14} aria-hidden="true" />
                    <span>{audit.message}</span>
                    <small>{audit.actor}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-copy">
                <History size={15} aria-hidden="true" /> 暂无相关审计事件
              </p>
            )}
          </section>
        </div>
      )}
    </DetailDrawer>
  );
}

function valueOrUnrecorded(value: string | null, field: string) {
  return value ?? missing(field);
}

function missing(field: string) {
  return (
    <span className="unrecorded-value" title={`后端当前未提供${field}字段`}>
      未提供
    </span>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "short",
    hour12: false,
  }).format(new Date(value));
}

function hostAnomalyLabel(status: string) {
  if (status === "UNAVAILABLE") return "主机不可达";
  if (status === "STOPPED") return "关联服务已停止";
  if (status === "DEGRADED") return "运行状态降级";
  return status;
}
