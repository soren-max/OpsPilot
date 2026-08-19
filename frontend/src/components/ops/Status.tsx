import { AlertTriangle, CheckCircle2, CircleDashed, Clock3, Info, XCircle } from "lucide-react";

export type StatusDomain = "task" | "service" | "host" | "audit" | "generic";
export type StatusTone =
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "running"
  | "pending"
  | "offline"
  | "unknown"
  | "neutral";

function statusTone(status: string): StatusTone {
  if (
    [
      "SUCCEEDED",
      "SUCCESS",
      "HEALTHY",
      "OK",
      "READY",
      "CONFIGURED",
      "FOUND",
      "EXECUTABLE",
      "AVAILABLE",
      "NOT_REQUIRED",
    ].includes(status)
  )
    return "success";
  if (["RUNNING", "INSPECTING"].includes(status)) return "running";
  if (["PENDING", "QUEUED"].includes(status)) return "pending";
  if (["STOPPED", "OFFLINE", "DISABLED", "CANCELLED", "UNAVAILABLE"].includes(status)) {
    return "offline";
  }
  if (status === "UNKNOWN" || status === "NOT_CONNECTED") return "unknown";
  if (["PARTIALLY_SUCCEEDED", "DEGRADED", "TIMED_OUT"].includes(status)) return "warning";
  if (
    ["NOT_READY", "NOT_CONFIGURED", "NOT_FOUND", "NOT_EXECUTABLE", "PENDING_CONFIRMATION"].includes(
      status,
    )
  )
    return "warning";
  if (["FAILED", "ERROR", "REJECTED", "UNHEALTHY"].includes(status)) return "danger";
  return "unknown";
}

function statusLabel(status: string, domain: StatusDomain) {
  const labels: Record<StatusDomain, Record<string, string>> = {
    task: {
      SUCCEEDED: "执行成功",
      PARTIALLY_SUCCEEDED: "部分成功",
      FAILED: "执行失败",
      TIMED_OUT: "执行超时",
      PENDING: "等待执行",
      RUNNING: "执行中",
      CANCELLED: "已取消",
      REJECTED: "已拒绝",
      UNKNOWN: "状态未知",
    },
    service: {
      RUNNING: "运行正常",
      STOPPED: "已停止",
      DEGRADED: "运行异常",
      UNAVAILABLE: "运行异常",
      UNKNOWN: "状态未知",
      OFFLINE: "服务离线",
      DISABLED: "服务已禁用",
    },
    host: {
      RUNNING: "运行正常",
      STOPPED: "服务已停止",
      UNAVAILABLE: "主机不可达",
      UNKNOWN: "状态未知",
      OFFLINE: "主机离线",
      DISABLED: "主机已禁用",
    },
    audit: { SUCCESS: "成功", WARNING: "风险提示", FAILED: "失败" },
    generic: {
      SUCCEEDED: "成功",
      SUCCESS: "正常",
      HEALTHY: "正常",
      OK: "正常",
      READY: "就绪",
      CONFIGURED: "已配置",
      FOUND: "已找到",
      EXECUTABLE: "可执行",
      AVAILABLE: "可用",
      NOT_REQUIRED: "不适用",
      NOT_READY: "未就绪",
      NOT_CONFIGURED: "未配置",
      NOT_FOUND: "未找到",
      NOT_EXECUTABLE: "不可执行",
      PENDING_CONFIRMATION: "等待确认",
      PARTIALLY_SUCCEEDED: "部分成功",
      FAILED: "失败",
      TIMED_OUT: "超时",
      PENDING: "待执行",
      RUNNING: "运行中",
      CANCELLED: "已取消",
      REJECTED: "已拒绝",
      UNKNOWN: "未接入",
      NOT_CONNECTED: "未连接",
      UNAVAILABLE: "不可用",
      DEGRADED: "降级",
      OFFLINE: "离线",
      DISABLED: "已禁用",
      ERROR: "错误",
      UNHEALTHY: "异常",
    },
  };
  return labels[domain][status] ?? status;
}

export function StatusBadge({
  status,
  compact = false,
  domain = "generic",
}: {
  status: string;
  compact?: boolean;
  domain?: StatusDomain;
}) {
  const tone = statusTone(status);
  const Icon =
    tone === "success"
      ? CheckCircle2
      : tone === "danger"
        ? XCircle
        : tone === "warning"
          ? AlertTriangle
          : tone === "running" || tone === "pending"
            ? Clock3
            : tone === "info"
              ? Info
              : CircleDashed;
  return (
    <span className={`status-badge status-badge--${tone}`} title={status}>
      <Icon size={compact ? 12 : 14} aria-hidden="true" />
      <span>{statusLabel(status, domain)}</span>
    </span>
  );
}

export function EnvironmentBadge({
  name,
  level = "DEVELOPMENT",
}: {
  name: string;
  level?: "DEVELOPMENT" | "TEST" | "PRODUCTION";
}) {
  const production = level === "PRODUCTION";
  return (
    <span className={`environment-badge ${production ? "environment-badge--production" : ""}`}>
      <span aria-hidden="true" />
      {name}
      {production && <strong>生产</strong>}
    </span>
  );
}

export function ExecutorBadge({ executor }: { executor?: string }) {
  return <span className="executor-badge">{executor || "未提供"}</span>;
}

export function PolicyBadge({
  enabled,
  children,
}: {
  enabled: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`policy-badge ${enabled ? "policy-badge--enabled" : "policy-badge--restricted"}`}
    >
      {enabled ? (
        <CheckCircle2 size={13} aria-hidden="true" />
      ) : (
        <AlertTriangle size={13} aria-hidden="true" />
      )}
      {children}
    </span>
  );
}
