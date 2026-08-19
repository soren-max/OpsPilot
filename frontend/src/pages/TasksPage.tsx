import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Filter, TerminalSquare } from "lucide-react";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { tasksApi } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/PageState";
import {
  DataTable,
  DetailDrawer,
  ExecutionChain,
  FilterBar,
  InlineNotice,
  PageHeader,
  SearchInput,
  PageSection,
  StatusBadge,
  TablePagination,
  TaskLogPanel,
  terminalTaskStatuses,
} from "../components/OpsUI";
import type { SecurityContext, Task } from "../types";
import { queryKeys } from "../query/queryKeys";

const PAGE_SIZE = 15;

export function TasksPage({
  environmentId,
  security,
}: {
  environmentId: string;
  security: SecurityContext;
}) {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const status = params.get("status") ?? "ALL";
  const selectedId = params.get("task");
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const tasks = useQuery({
    queryKey: queryKeys.tasks,
    queryFn: tasksApi.list,
    refetchInterval: 3_000,
  });
  const approvals = useQuery({
    queryKey: queryKeys.operationRequests,
    queryFn: tasksApi.operationRequests,
    refetchInterval: 3_000,
  });
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "reject" | "cancel" }) =>
      decision === "approve"
        ? tasksApi.approveOperationRequest(id)
        : decision === "reject"
          ? tasksApi.rejectOperationRequest(id)
          : tasksApi.cancelOperationRequest(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.operationRequests });
      void queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
      void queryClient.invalidateQueries({ queryKey: queryKeys.audits });
    },
  });
  const detail = useQuery({
    queryKey: queryKeys.task(selectedId),
    queryFn: () => tasksApi.detail(selectedId!),
    enabled: Boolean(selectedId),
    refetchInterval: (query) =>
      query.state.data && terminalTaskStatuses.has(query.state.data.status) ? false : 1_000,
  });
  const setParam = (key: string, value: string) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (!value || value === "ALL" || (key === "page" && value === "1")) next.delete(key);
      else next.set(key, value);
      if (!["task", "page"].includes(key)) next.delete("page");
      return next;
    });
  const filtered = useMemo(
    () =>
      (tasks.data ?? [])
        .filter(
          (task) =>
            task.environment_id === environmentId &&
            (status === "ALL" || task.status === status) &&
            `${task.id} ${task.action} ${task.requested_by}`
              .toLowerCase()
              .includes(search.toLowerCase()),
        )
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [tasks.data, environmentId, search, status],
  );
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const clearFilters = () => setParams(selectedId ? { task: selectedId } : {});
  return (
    <div className="page-stack data-page tasks-page">
      <PageHeader
        title="任务中心"
        description="从任务创建、Worker 领取、目标执行到结果归档跟踪完整执行链路。"
        actions={
          <span className="page-header__status">
            <TerminalSquare size={16} /> 任务每 3 秒刷新
          </span>
        }
      />
      <PageSection
        title="审批请求"
        description="管理员可按后端权限和审批策略审批、驳回或取消待处理写操作"
      >
        {approvals.isLoading ? (
          <LoadingState variant="table" />
        ) : approvals.error ? (
          <ErrorState error={approvals.error} onRetry={() => void approvals.refetch()} />
        ) : approvals.data?.length ? (
          <DataTable ariaLabel="审批请求">
            <thead>
              <tr>
                <th>请求 ID</th>
                <th>动作</th>
                <th>原因</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {approvals.data.map((item) => (
                <tr key={item.id}>
                  <td className="mono">{item.id.slice(0, 8)}</td>
                  <td>
                    <span className="type-tag">{item.action}</span>
                  </td>
                  <td>{item.reason ?? "—"}</td>
                  <td>
                    <StatusBadge status={item.status} domain="task" />
                  </td>
                  <td>
                    {item.status === "PENDING" && (
                      <div className="table-row-actions">
                        {security.approval.can_approve && (
                          <button
                            onClick={() => decide.mutate({ id: item.id, decision: "approve" })}
                          >
                            审批
                          </button>
                        )}
                        {security.approval.can_reject && (
                          <button
                            onClick={() => decide.mutate({ id: item.id, decision: "reject" })}
                          >
                            驳回
                          </button>
                        )}
                        {security.approval.can_cancel && (
                          <button
                            onClick={() => decide.mutate({ id: item.id, decision: "cancel" })}
                          >
                            取消
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <EmptyState title="暂无审批请求" message="start/stop 请求会显示在这里。" />
        )}
      </PageSection>
      <PageSection
        title="执行历史"
        description="运行中任务详情每秒刷新；完成后停止轮询"
        className="operations-table-card"
      >
        <FilterBar>
          <SearchInput
            value={search}
            onChange={(value) => setParam("search", value)}
            placeholder="搜索任务 ID、操作或执行人"
            ariaLabel="搜索任务"
          />
          <span className="filter-label">
            <Filter size={15} /> 状态
          </span>
          <select
            value={status}
            onChange={(event) => setParam("status", event.target.value)}
            aria-label="按任务状态筛选"
          >
            <option value="ALL">全部</option>
            <option value="PENDING">待执行</option>
            <option value="RUNNING">执行中</option>
            <option value="SUCCEEDED">成功</option>
            <option value="PARTIALLY_SUCCEEDED">部分成功</option>
            <option value="FAILED">失败</option>
            <option value="TIMED_OUT">超时</option>
            <option value="CANCELLED">已取消</option>
            <option value="REJECTED">已拒绝</option>
          </select>
          <span className="filter-bar__count">{filtered.length} 条记录</span>
        </FilterBar>
        {tasks.isLoading ? (
          <LoadingState variant="table" />
        ) : tasks.error ? (
          <ErrorState error={tasks.error} onRetry={() => void tasks.refetch()} />
        ) : !filtered.length ? (
          <EmptyState
            title={tasks.data?.length ? "没有匹配任务" : "暂无执行任务"}
            message={
              tasks.data?.length ? "请调整任务搜索或状态筛选。" : "可从运维总览创建状态检查任务。"
            }
            action={
              tasks.data?.length ? (
                <button className="button button--secondary" onClick={clearFilters}>
                  清除筛选
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            <DataTable ariaLabel="任务执行历史">
              <thead>
                <tr>
                  <th>任务 ID</th>
                  <th>操作类型</th>
                  <th>环境</th>
                  <th>资产</th>
                  <th>服务</th>
                  <th>发起人</th>
                  <th>开始时间</th>
                  <th>耗时</th>
                  <th>执行状态</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <button
                        className="entity-link mono table-entity-button"
                        onClick={() => setParam("task", task.id)}
                      >
                        {task.id.slice(0, 8)}
                      </button>
                    </td>
                    <td>
                      <span className="type-tag">{task.action}</span>
                    </td>
                    <td>{task.environment_name}</td>
                    <td className="compact-target-cell">{summarizeTargets(task, "host")}</td>
                    <td className="compact-target-cell">{summarizeTargets(task, "service")}</td>
                    <td>{task.requested_by}</td>
                    <td>{formatDate(task.started_at ?? task.created_at)}</td>
                    <td className="mono">{duration(task)}</td>
                    <td>
                      <StatusBadge status={task.status} domain="task" />
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
      <TaskDrawer
        task={detail.data}
        loading={detail.isLoading}
        error={detail.error}
        open={Boolean(selectedId)}
        onRetry={() => void detail.refetch()}
        onClose={() => setParam("task", "")}
        canCancel={security.permissions.includes("task.cancel")}
      />
    </div>
  );
}

function TaskDrawer({
  task,
  loading,
  error,
  open,
  onRetry,
  onClose,
  canCancel,
}: {
  task: Task | undefined;
  loading: boolean;
  error: Error | null;
  open: boolean;
  onRetry: () => void;
  onClose: () => void;
  canCancel: boolean;
}) {
  const queryClient = useQueryClient();
  const cancelTask = useMutation({
    mutationFn: () => tasksApi.cancel(task!.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
      void queryClient.invalidateQueries({ queryKey: queryKeys.task(task?.id ?? null) });
    },
  });
  const logs = useQuery({
    queryKey: queryKeys.taskLogs(task?.id),
    queryFn: () => tasksApi.logs(task?.id ?? ""),
    enabled: Boolean(task?.id && open),
    refetchInterval: task && !terminalTaskStatuses.has(task.status) ? 1_000 : false,
  });
  const succeeded =
    task?.targets.filter((target) => ["SUCCEEDED", "SUCCESS"].includes(target.status)).length ?? 0;
  const failed =
    task?.targets.filter((target) => ["FAILED", "TIMED_OUT", "UNAVAILABLE"].includes(target.status))
      .length ?? 0;
  return (
    <DetailDrawer
      open={open}
      title={task ? `任务 ${task.id.slice(0, 8)}` : "任务详情"}
      subtitle={task ? `${task.action} · ${task.environment_name} · ${task.id}` : "正在读取任务"}
      className="detail-drawer--task"
      onClose={onClose}
    >
      {loading ? (
        <LoadingState variant="cards" label="正在加载目标级结果" />
      ) : error ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : task ? (
        <div className="drawer-sections task-detail">
          <section className="task-overview task-overview--dense" aria-label="执行摘要">
            <div className="task-overview__status">
              <span>总体状态</span>
              <StatusBadge status={task.status} domain="task" />
            </div>
            <div>
              <span>目标数量</span>
              <strong>{task.targets.length}</strong>
            </div>
            {canCancel && ["PENDING", "RUNNING"].includes(task.status) && (
              <div>
                <span>任务控制</span>
                <button
                  className="button button--danger"
                  disabled={cancelTask.isPending}
                  onClick={() => cancelTask.mutate()}
                >
                  {cancelTask.isPending ? "取消中…" : "取消任务"}
                </button>
              </div>
            )}
            <div>
              <span>成功数量</span>
              <strong className="success-text">{succeeded}</strong>
            </div>
            <div>
              <span>失败数量</span>
              <strong className={failed ? "danger-text" : ""}>{failed}</strong>
            </div>
            <div>
              <span>总耗时</span>
              <strong className="mono">{duration(task)}</strong>
            </div>
            <div>
              <span>操作人</span>
              <strong>{task.requested_by}</strong>
            </div>
            <div>
              <span>Executor</span>
              <strong className="mono">未记录</strong>
            </div>
          </section>
          <section className="task-detail__section task-detail__section--failure">
            <h3>错误码与解析</h3>
            <dl className="failure-evidence">
              <div>
                <dt>Error code</dt>
                <dd className="unrecorded-value">未提供</dd>
              </div>
              <div>
                <dt>Exit code</dt>
                <dd className="mono">{summarizeExitCodes(logs.data)}</dd>
              </div>
              <div>
                <dt>Parser</dt>
                <dd className="unrecorded-value">未提供</dd>
              </div>
            </dl>
            {task.error_message ? (
              <InlineNotice title="任务错误" tone="danger">
                {task.error_message}
              </InlineNotice>
            ) : (
              <p className="muted-copy">当前任务没有后端任务级错误信息。</p>
            )}
          </section>
          <section className="task-detail__section task-detail__section--output">
            <h3>stderr / stdout</h3>
            <TaskLogPanel logs={logs.data} targets={task.targets} failureFirst />
            {logs.data?.length ? (
              <div className="task-log-metadata" aria-label="任务日志元数据">
                {logs.data.map((log) => (
                  <span key={log.id}>
                    {log.dry_run ? "模拟 Dry Run" : "隔离测试真实执行"} · {log.stream} · 退出码{" "}
                    {log.exit_code ?? "—"}
                  </span>
                ))}
              </div>
            ) : null}
          </section>
          <section className="task-detail__section task-detail__section--timeline">
            <h3>结构化执行链</h3>
            <ExecutionChain task={task} />
          </section>
          <section className="task-detail__section task-detail__section--results">
            <h3>目标级结果</h3>
            {task.targets.length ? (
              <DataTable ariaLabel="目标级结果">
                <thead>
                  <tr>
                    <th>服务 / 主机</th>
                    <th>状态</th>
                    <th>耗时</th>
                    <th>错误原因</th>
                  </tr>
                </thead>
                <tbody>
                  {task.targets.map((target) => (
                    <tr key={target.id}>
                      <td>
                        <strong>{target.service_name}</strong>
                        <small className="mono">{target.host_name}</small>
                      </td>
                      <td>
                        <StatusBadge status={target.status} domain="task" />
                      </td>
                      <td className="mono">
                        {target.duration_ms === null ? "—" : formatMilliseconds(target.duration_ms)}
                      </td>
                      <td className="error-reason">{target.error_message ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            ) : (
              <EmptyState title="等待目标结果" message="Worker 尚未写入目标级结果。" />
            )}
          </section>
          <section className="task-detail__section task-detail__section--audit">
            <h3>审计信息</h3>
            <p className="muted-copy">
              执行人：{task.requested_by}。任务创建与状态变化均已写入审计日志。
            </p>
          </section>
        </div>
      ) : null}
    </DetailDrawer>
  );
}

function formatDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "medium" }).format(
        new Date(value),
      )
    : "—";
}

function formatMilliseconds(value: number) {
  if (value < 1_000) return `${value} ms`;
  if (value < 60_000) return `${(value / 1_000).toFixed(1)} s`;
  return `${Math.floor(value / 60_000)}m ${Math.floor((value % 60_000) / 1_000)}s`;
}

function duration(task: Task) {
  if (task.started_at && task.finished_at)
    return formatMilliseconds(
      Math.max(0, new Date(task.finished_at).getTime() - new Date(task.started_at).getTime()),
    );
  return task.status === "RUNNING" ? "执行中" : task.status === "PENDING" ? "等待中" : "—";
}

function summarizeExitCodes(logs: { exit_code: number | null }[] | undefined) {
  const exitCodes = [...new Set((logs ?? []).flatMap((log) => log.exit_code ?? []))];
  return exitCodes.length ? exitCodes.join("、") : "未记录";
}

function summarizeTargets(task: Task, field: "host" | "service") {
  const values = [
    ...new Set(
      task.targets.map((target) => (field === "host" ? target.host_name : target.service_name)),
    ),
  ];
  if (!values.length) return <span className="unrecorded-value">未记录</span>;
  return values.length > 2
    ? `${values.slice(0, 2).join("、")} +${values.length - 2}`
    : values.join("、");
}
