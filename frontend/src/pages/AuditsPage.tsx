import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck, Filter } from "lucide-react";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { auditsApi, tasksApi } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import {
  DataTable,
  DetailDrawer,
  FilterBar,
  InlineNotice,
  PageHeader,
  SearchInput,
  PageSection,
  StatusBadge,
  TablePagination,
  TaskLogPanel,
} from "../components/OpsUI";
import { queryKeys } from "../query/queryKeys";
import type { Audit, Task } from "../types";

const PAGE_SIZE = 20;

export function AuditsPage({ environmentId }: { environmentId: string }) {
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const eventType = params.get("event") ?? "ALL";
  const action = params.get("action") ?? "ALL";
  const range = params.get("range") ?? "7d";
  const result = params.get("result") ?? "ALL";
  const selectedId = params.get("audit") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const audits = useQuery({
    queryKey: queryKeys.audits,
    queryFn: auditsApi.list,
    refetchInterval: 5_000,
  });
  const tasks = useQuery({
    queryKey: queryKeys.tasks,
    queryFn: tasksApi.list,
    refetchInterval: 5_000,
  });
  const taskMap = useMemo(() => new Map(tasks.data?.map((task) => [task.id, task])), [tasks.data]);
  const taskIds = useMemo(
    () =>
      new Set(
        tasks.data?.filter((item) => item.environment_id === environmentId).map((item) => item.id),
      ),
    [tasks.data, environmentId],
  );
  const setParam = (key: string, value: string) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      const defaults: Record<string, string> = {
        event: "ALL",
        action: "ALL",
        result: "ALL",
        range: "7d",
        page: "1",
      };
      if (!value || value === defaults[key]) next.delete(key);
      else next.set(key, value);
      if (!["audit", "page"].includes(key)) next.delete("page");
      return next;
    });
  const filtered = useMemo(() => {
    const rangeMs: Record<string, number> = {
      "24h": 86_400_000,
      "7d": 604_800_000,
      "30d": 2_592_000_000,
    };
    const cutoff = range === "ALL" ? 0 : Date.now() - (rangeMs[range] ?? rangeMs["7d"]!);
    return (audits.data ?? [])
      .filter((audit) => {
        const task = audit.task_id ? taskMap.get(audit.task_id) : undefined;
        const resultMatch =
          result === "ALL" ||
          (result === "SUCCESS"
            ? task?.status === "SUCCEEDED"
            : task &&
              ["FAILED", "TIMED_OUT", "PARTIALLY_SUCCEEDED", "REJECTED"].includes(task.status));
        return (
          (audit.task_id ? taskIds.has(audit.task_id) : true) &&
          (eventType === "ALL" || audit.event_type === eventType) &&
          (action === "ALL" || task?.action === action) &&
          resultMatch &&
          new Date(audit.created_at).getTime() >= cutoff &&
          `${audit.actor} ${audit.message} ${audit.task_id ?? ""} ${task?.action ?? ""} ${targetNames(task)}`
            .toLowerCase()
            .includes(search.toLowerCase())
        );
      })
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [audits.data, eventType, action, range, result, search, taskIds, taskMap]);
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const selectedAudit = filtered.find((audit) => audit.id === selectedId);
  const selectedTask = selectedAudit?.task_id ? taskMap.get(selectedAudit.task_id) : undefined;
  const loading = audits.isLoading || tasks.isLoading;
  const error = audits.error ?? tasks.error;

  return (
    <div className="page-stack data-page audit-page">
      <PageHeader
        title="操作审计"
        description="以企业审计表格追溯操作者、环境、目标、动作和执行结果；未采集字段不会补造。"
        actions={
          <span className="page-header__status">
            <ClipboardCheck size={16} /> 每 5 秒刷新
          </span>
        }
      />
      <PageSection
        title="审计记录"
        description="按时间倒序展示当前环境的可追责操作"
        className="operations-table-card"
      >
        <FilterBar>
          <SearchInput
            value={search}
            onChange={(value) => setParam("search", value)}
            placeholder="搜索用户、任务、动作或目标"
            ariaLabel="搜索审计记录"
          />
          <span className="filter-label">
            <Filter size={15} /> 筛选
          </span>
          <select
            value={eventType}
            onChange={(event) => setParam("event", event.target.value)}
            aria-label="按审计事件筛选"
          >
            <option value="ALL">全部事件</option>
            <option value="TASK_CREATED">任务创建</option>
            <option value="TASK_STATUS_CHANGED">状态变化</option>
          </select>
          <select
            value={action}
            onChange={(event) => setParam("action", event.target.value)}
            aria-label="按操作类型筛选"
          >
            <option value="ALL">全部动作</option>
            <option value="status">status</option>
            <option value="status_all">status_all</option>
            <option value="status_service">status_service</option>
            <option value="status_service_hosts">status_service_hosts</option>
            <option value="start">start</option>
            <option value="stop">stop</option>
          </select>
          <select
            value={result}
            onChange={(event) => setParam("result", event.target.value)}
            aria-label="按结果筛选"
          >
            <option value="ALL">全部结果</option>
            <option value="SUCCESS">成功</option>
            <option value="FAILED">异常</option>
          </select>
          <select
            value={range}
            onChange={(event) => setParam("range", event.target.value)}
            aria-label="按时间范围筛选"
          >
            <option value="24h">最近 24 小时</option>
            <option value="7d">最近 7 天</option>
            <option value="30d">最近 30 天</option>
            <option value="ALL">全部时间</option>
          </select>
          <span className="filter-bar__count">{filtered.length} 条事件</span>
        </FilterBar>
        {loading ? (
          <LoadingState variant="table" />
        ) : error ? (
          <ErrorState
            error={error}
            onRetry={() => {
              void audits.refetch();
              void tasks.refetch();
            }}
          />
        ) : !filtered.length ? (
          <EmptyState
            title={audits.data?.length ? "没有匹配事件" : "暂无审计记录"}
            message={
              audits.data?.length ? "请扩大时间范围或调整筛选条件。" : "当前环境尚未产生审计事件。"
            }
            action={
              audits.data?.length ? (
                <button className="button button--secondary" onClick={() => setParams({})}>
                  清除筛选
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            <DataTable ariaLabel="企业操作审计列表">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作人</th>
                  <th>来源 IP</th>
                  <th>环境</th>
                  <th>资产</th>
                  <th>服务</th>
                  <th>Action</th>
                  <th>执行结果</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {visible.map((audit) => {
                  const task = audit.task_id ? taskMap.get(audit.task_id) : undefined;
                  return (
                    <tr key={audit.id}>
                      <td>{formatDate(audit.created_at)}</td>
                      <td>
                        <strong>{audit.actor}</strong>
                      </td>
                      <td className="mono">
                        {detailValue(audit, ["source_ip", "client_ip", "ip"])}
                      </td>
                      <td>
                        {task?.environment_name ?? <span className="unrecorded-value">未记录</span>}
                      </td>
                      <td className="compact-target-cell">{targetSummary(task, "host")}</td>
                      <td className="compact-target-cell">{targetSummary(task, "service")}</td>
                      <td>
                        <span className="type-tag">
                          {task?.action ?? eventLabel(audit.event_type)}
                        </span>
                      </td>
                      <td>
                        {task ? (
                          <StatusBadge status={task.status} domain="task" compact />
                        ) : (
                          <span className="unrecorded-value">未记录</span>
                        )}
                      </td>
                      <td>
                        <button className="row-action" onClick={() => setParam("audit", audit.id)}>
                          详情
                        </button>
                      </td>
                    </tr>
                  );
                })}
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
      <AuditDrawer
        audit={selectedAudit}
        task={selectedTask}
        onClose={() => setParam("audit", "")}
      />
    </div>
  );
}

function AuditDrawer({
  audit,
  task,
  onClose,
}: {
  audit: Audit | undefined;
  task: Task | undefined;
  onClose: () => void;
}) {
  const logs = useQuery({
    queryKey: queryKeys.taskLogs(task?.id),
    queryFn: () => tasksApi.logs(task?.id ?? ""),
    enabled: Boolean(audit && task?.id),
  });
  return (
    <DetailDrawer
      open={Boolean(audit)}
      title={audit ? eventLabel(audit.event_type) : "审计详情"}
      subtitle={audit ? `${audit.id} · ${formatDate(audit.created_at)}` : undefined}
      onClose={onClose}
    >
      {audit && (
        <div className="drawer-sections audit-record-detail">
          <section className="audit-evidence__status">
            <h3>状态与身份</h3>
            <div className="audit-primary-status">
              {task ? <StatusBadge status={task.status} domain="task" /> : missingValue("执行状态")}
              <span>{audit.message}</span>
            </div>
            <dl className="key-value">
              <div>
                <dt>操作人</dt>
                <dd>{audit.actor}</dd>
              </div>
              <div>
                <dt>来源 IP</dt>
                <dd>{detailValue(audit, ["source_ip", "client_ip", "ip"])}</dd>
              </div>
              <div>
                <dt>角色</dt>
                <dd>{detailValue(audit, ["role"])}</dd>
              </div>
              <div>
                <dt>环境</dt>
                <dd>{task?.environment_name ?? "未记录"}</dd>
              </div>
              <div>
                <dt>Action</dt>
                <dd>{task?.action ?? "未记录"}</dd>
              </div>
              <div>
                <dt>Executor</dt>
                <dd>{detailValue(audit, ["executor"])}</dd>
              </div>
              <div>
                <dt>Task ID</dt>
                <dd className="mono">{audit.task_id ?? "未记录"}</dd>
              </div>
              <div>
                <dt>Request ID</dt>
                <dd className="mono">{detailValue(audit, ["request_id"])}</dd>
              </div>
              <div>
                <dt>执行结果</dt>
                <dd>
                  {task ? <StatusBadge status={task.status} domain="task" compact /> : "未记录"}
                </dd>
              </div>
              <div>
                <dt>耗时</dt>
                <dd className="mono">{task ? auditDuration(task) : "未记录"}</dd>
              </div>
            </dl>
          </section>
          <section className="audit-evidence__failure">
            <h3>错误码与解析</h3>
            <dl className="failure-evidence">
              <div>
                <dt>Error code</dt>
                <dd className="mono">{detailString(audit, ["error_code", "code"]) ?? "未提供"}</dd>
              </div>
              <div>
                <dt>Exit code</dt>
                <dd className="mono">{summarizeAuditExitCodes(logs.data)}</dd>
              </div>
              <div>
                <dt>Parser</dt>
                <dd>{detailString(audit, ["parser", "parser_name"]) ?? "未提供"}</dd>
              </div>
            </dl>
            {task?.error_message && (
              <InlineNotice title="任务错误" tone="danger">
                {task.error_message}
              </InlineNotice>
            )}
          </section>
          <section className="audit-evidence__output">
            <h3>stderr / stdout</h3>
            {logs.error ? (
              <InlineNotice title="执行输出不可用" tone="warning">
                {logs.error.message}
              </InlineNotice>
            ) : task ? (
              <TaskLogPanel logs={logs.data} targets={task.targets} failureFirst />
            ) : (
              <EmptyState title="输出未提供" message="该审计事件没有关联任务输出。" />
            )}
          </section>
          <section className="audit-evidence__timeline">
            <h3>Timeline</h3>
            <ol className="audit-evidence-timeline">
              <li>
                <span>审计事件</span>
                <time>{formatDate(audit.created_at)}</time>
              </li>
              <li>
                <span>任务创建</span>
                <time>{task ? formatDate(task.created_at) : "未提供"}</time>
              </li>
              <li>
                <span>执行开始</span>
                <time>{task?.started_at ? formatDate(task.started_at) : "未提供"}</time>
              </li>
              <li>
                <span>执行结束</span>
                <time>{task?.finished_at ? formatDate(task.finished_at) : "未提供"}</time>
              </li>
            </ol>
          </section>
          <section className="audit-evidence__targets">
            <h3>操作目标</h3>
            {task?.targets.length ? (
              <DataTable ariaLabel="审计操作目标">
                <thead>
                  <tr>
                    <th>资产</th>
                    <th>服务</th>
                    <th>状态</th>
                    <th>耗时</th>
                  </tr>
                </thead>
                <tbody>
                  {task.targets.map((target) => (
                    <tr key={target.id}>
                      <td className="mono">{target.host_name}</td>
                      <td>{target.service_name}</td>
                      <td>
                        <StatusBadge status={target.status} domain="task" compact />
                      </td>
                      <td className="mono">
                        {target.duration_ms === null ? "未记录" : `${target.duration_ms} ms`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            ) : (
              <p className="muted-copy">目标未记录。</p>
            )}
          </section>
          <section>
            <h3>原始审计详情</h3>
            <pre className="audit-json">{JSON.stringify(audit.details, null, 2)}</pre>
          </section>
        </div>
      )}
    </DetailDrawer>
  );
}

function detailValue(audit: Audit, keys: string[]) {
  for (const key of keys) {
    const value = audit.details[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return <span className="unrecorded-value">未记录</span>;
}

function detailString(audit: Audit, keys: string[]) {
  for (const key of keys) {
    const value = audit.details[key];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number") return String(value);
  }
  return null;
}

function summarizeAuditExitCodes(logs: { exit_code: number | null }[] | undefined) {
  const values = [...new Set((logs ?? []).flatMap((log) => log.exit_code ?? []))];
  return values.length ? values.join("、") : "未提供";
}

function missingValue(field: string) {
  return (
    <span className="unrecorded-value" title={`后端未提供${field}`}>
      未提供
    </span>
  );
}

function targetSummary(task: Task | undefined, field: "host" | "service") {
  if (!task?.targets.length) return <span className="unrecorded-value">未记录</span>;
  const values = [
    ...new Set(
      task.targets.map((target) => (field === "host" ? target.host_name : target.service_name)),
    ),
  ];
  return values.length > 2
    ? `${values.slice(0, 2).join("、")} +${values.length - 2}`
    : values.join("、");
}

function targetNames(task: Task | undefined) {
  return task?.targets.flatMap((target) => [target.host_name, target.service_name]).join(" ") ?? "";
}

function auditDuration(task: Task) {
  if (!task.started_at || !task.finished_at) return task.status === "RUNNING" ? "执行中" : "未记录";
  const milliseconds = Math.max(
    0,
    new Date(task.finished_at).getTime() - new Date(task.started_at).getTime(),
  );
  return milliseconds < 1_000 ? `${milliseconds} ms` : `${(milliseconds / 1_000).toFixed(1)} s`;
}

function eventLabel(value: string) {
  return (
    ({ TASK_CREATED: "任务创建", TASK_STATUS_CHANGED: "状态变化" } as Record<string, string>)[
      value
    ] ?? value
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "medium",
    hour12: false,
  }).format(new Date(value));
}
