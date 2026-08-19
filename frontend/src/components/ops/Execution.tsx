/* eslint-disable react-refresh/only-export-components -- shared task utilities are intentional */
import { Check, CircleDashed, Copy, ShieldCheck, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import type { OperationTarget, Task, TaskLog } from "../../types";

export const terminalTaskStatuses = new Set([
  "SUCCEEDED",
  "PARTIALLY_SUCCEEDED",
  "FAILED",
  "TIMED_OUT",
  "CANCELLED",
  "REJECTED",
]);

type ChainState = "complete" | "active" | "failed" | "pending";

export function ExecutionChain({ task }: { task: Task }) {
  const rejected = task.status === "REJECTED";
  const finished = Boolean(task.finished_at);
  const started = Boolean(task.started_at);
  const failed = ["FAILED", "TIMED_OUT", "PARTIALLY_SUCCEEDED"].includes(task.status);
  const steps: Array<{
    label: string;
    detail: string;
    state: ChainState;
  }> = [
    {
      label: "用户请求",
      detail: `${task.requested_by} · ${formatDate(task.created_at)}`,
      state: "complete",
    },
    {
      label: "权限校验",
      detail: rejected ? "策略拒绝，请查看审计记录" : "任务已受理",
      state: rejected ? "failed" : "complete",
    },
    {
      label: "Executor",
      detail: rejected ? "未进入执行器" : "执行器类型未记录",
      state: rejected ? "pending" : started ? "complete" : "pending",
    },
    {
      label: "脚本执行",
      detail: rejected ? "未执行" : started ? `${task.targets.length} 个目标` : "等待 Worker",
      state: rejected ? "pending" : finished ? "complete" : started ? "active" : "pending",
    },
    {
      label: "结果解析",
      detail: finished ? task.status : "等待结果",
      state: finished ? (failed ? "failed" : "complete") : "pending",
    },
  ];

  return (
    <ol className="execution-chain" aria-label="任务结构化执行链">
      {steps.map((step, index) => {
        const Icon =
          step.state === "complete"
            ? Check
            : step.state === "failed"
              ? XCircle
              : step.state === "active"
                ? ShieldCheck
                : CircleDashed;
        return (
          <li key={step.label} className={`execution-chain__step is-${step.state}`}>
            <span className="execution-chain__index">{index + 1}</span>
            <Icon size={15} aria-hidden="true" />
            <div>
              <strong>{step.label}</strong>
              <small>{step.detail}</small>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function TaskLogPanel({
  logs,
  targets,
  failureFirst = false,
}: {
  logs: TaskLog[] | undefined;
  targets: OperationTarget[];
  failureFirst?: boolean;
}) {
  const [stream, setStream] = useState<"ALL" | "stdout" | "stderr">("ALL");
  const [targetId, setTargetId] = useState("ALL");
  const [wrapped, setWrapped] = useState(true);
  const targetMap = useMemo(() => new Map(targets.map((target) => [target.id, target])), [targets]);
  const entries = useMemo(() => {
    if (logs?.length) return logs.filter((log) => log.message);
    return targets.flatMap((target) => [
      ...(target.output
        ? [
            {
              id: `${target.id}-stdout`,
              task_id: "",
              target_id: target.id,
              stream: "stdout",
              message: target.output,
              exit_code: null,
              dry_run: false,
              created_at: "",
            },
          ]
        : []),
      ...(target.error_message
        ? [
            {
              id: `${target.id}-stderr`,
              task_id: "",
              target_id: target.id,
              stream: "stderr",
              message: target.error_message,
              exit_code: null,
              dry_run: false,
              created_at: "",
            },
          ]
        : []),
    ]);
  }, [logs, targets]);
  const visible = entries
    .filter(
      (entry) =>
        (stream === "ALL" || entry.stream === stream) &&
        (targetId === "ALL" || entry.target_id === targetId),
    )
    .sort((left, right) =>
      failureFirst ? Number(right.stream === "stderr") - Number(left.stream === "stderr") : 0,
    );
  const text = visible
    .map((entry) => {
      const target = entry.target_id ? targetMap.get(entry.target_id) : undefined;
      return `[${entry.stream}] [${target?.host_name ?? "任务级"}] ${entry.message}`;
    })
    .join("\n");

  return (
    <div
      className={`task-log-panel task-log-panel--structured ${wrapped ? "is-wrapped" : "is-nowrap"}`}
      aria-label="分类执行日志"
    >
      <header>
        <div className="task-log-filters">
          <select
            value={targetId}
            onChange={(event) => setTargetId(event.target.value)}
            aria-label="按执行目标筛选日志"
          >
            <option value="ALL">全部目标</option>
            {targets.map((target) => (
              <option key={target.id} value={target.id}>
                {target.host_name} / {target.service_name}
              </option>
            ))}
          </select>
          <select
            value={stream}
            onChange={(event) => setStream(event.target.value as typeof stream)}
            aria-label="按输出类型筛选日志"
          >
            <option value="ALL">stdout + stderr</option>
            <option value="stdout">stdout</option>
            <option value="stderr">stderr</option>
          </select>
        </div>
        <div className="task-log-actions">
          <button className="text-button" onClick={() => setWrapped((current) => !current)}>
            {wrapped ? "不折行" : "折行"}
          </button>
          <button
            className="text-button"
            disabled={!visible.length}
            onClick={() => void navigator.clipboard?.writeText(text)}
          >
            <Copy size={14} aria-hidden="true" /> 复制
          </button>
        </div>
      </header>
      <div className="task-log-entries">
        {visible.map((entry) => {
          const target = entry.target_id ? targetMap.get(entry.target_id) : undefined;
          return (
            <article key={entry.id} className={`task-log-entry task-log-entry--${entry.stream}`}>
              <div>
                <span>{entry.stream}</span>
                <strong>{target?.host_name ?? "任务级日志"}</strong>
                <small>{target?.service_name ?? "目标未记录"}</small>
                <code>exit {entry.exit_code ?? "未记录"}</code>
              </div>
              <pre>{entry.message}</pre>
            </article>
          );
        })}
        {!visible.length && <p className="task-log-empty">当前分类暂无执行输出。</p>}
      </div>
    </div>
  );
}

export const LogViewer = TaskLogPanel;

export function CodeBlock({ value, label = "代码" }: { value: string; label?: string }) {
  const [wrapped, setWrapped] = useState(true);
  return (
    <section className="code-block" aria-label={label}>
      <header>
        <strong>{label}</strong>
        <div>
          <button className="text-button" onClick={() => setWrapped((current) => !current)}>
            {wrapped ? "不折行" : "折行"}
          </button>
          <button
            className="text-button"
            onClick={() => void navigator.clipboard?.writeText(value)}
          >
            <Copy size={14} aria-hidden="true" /> 复制
          </button>
        </div>
      </header>
      <pre className={wrapped ? "is-wrapped" : ""}>{value || "无输出"}</pre>
    </section>
  );
}

export function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "medium" }).format(
    new Date(value),
  );
}
