import type { Asset, Audit, Service, ServiceStatusSnapshot, SystemHealth, Task } from "../types";

export interface DashboardRisk {
  id: "failed" | "timeout" | "rejected";
  label: string;
  description: string;
  count: number;
  status: "FAILED" | "TIMED_OUT" | "REJECTED";
}

export interface DashboardViewModel {
  assets: {
    total: number;
    healthy: number;
    abnormal: number;
    unknown: number;
    lastCheckedAt: string | null;
  };
  services: {
    running: number;
    stopped: number;
    unknown: number;
  };
  recentTasks: Task[];
  risks: DashboardRisk[];
  system: Array<{
    id: string;
    label: string;
    status: string;
    detail: string;
  }>;
}

export function buildDashboardViewModel(input: {
  assets: Asset[];
  services: Service[];
  tasks: Task[];
  audits: Audit[];
  snapshots: ServiceStatusSnapshot[];
  health?: SystemHealth;
}): DashboardViewModel {
  const { assets, services, tasks, audits, snapshots, health } = input;
  const latestObserved = snapshots.reduce<string | null>(
    (latest, item) =>
      !latest || Date.parse(item.observed_at) > Date.parse(latest) ? item.observed_at : latest,
    null,
  );
  const deniedAudits = audits.filter((item) =>
    `${item.event_type} ${item.message}`.toUpperCase().match(/DENIED|REJECTED|拒绝/),
  ).length;
  const rejectedTasks = tasks.filter((item) => item.status === "REJECTED").length;
  const failedTasks = tasks.filter((item) =>
    ["FAILED", "PARTIALLY_SUCCEEDED"].includes(item.status),
  ).length;
  const timedOutTasks = tasks.filter((item) => item.status === "TIMED_OUT").length;
  return {
    assets: {
      total: assets.length,
      healthy: assets.filter((item) => item.serviceCheckStatus === "RUNNING").length,
      abnormal: assets.filter((item) =>
        ["UNAVAILABLE", "FAILED", "DEGRADED", "STOPPED"].includes(item.serviceCheckStatus),
      ).length,
      unknown: assets.filter((item) => item.serviceCheckStatus === "UNKNOWN").length,
      lastCheckedAt: latestObserved,
    },
    services: {
      running: services.filter((item) => item.current_status === "RUNNING").length,
      stopped: services.filter((item) => item.current_status === "STOPPED").length,
      unknown: services.filter((item) => !["RUNNING", "STOPPED"].includes(item.current_status))
        .length,
    },
    recentTasks: [...tasks]
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .slice(0, 6),
    risks: [
      {
        id: "failed",
        label: "执行失败",
        description: "失败或部分成功任务",
        count: failedTasks,
        status: "FAILED",
      },
      {
        id: "timeout",
        label: "任务超时",
        description: "需要检查执行链路",
        count: timedOutTasks,
        status: "TIMED_OUT",
      },
      {
        id: "rejected",
        label: "权限拒绝",
        description: "任务或审计拒绝事件",
        count: Math.max(rejectedTasks, deniedAudits),
        status: "REJECTED",
      },
    ],
    system: [
      {
        id: "opspilot",
        label: "OPSPILOT 服务",
        status: health?.status?.toUpperCase() ?? "UNKNOWN",
        detail: health ? "API 健康检查正常" : "健康接口不可用",
      },
      {
        id: "worker",
        label: "Worker",
        status: "UNKNOWN",
        detail: "状态未接入",
      },
      {
        id: "database",
        label: "数据库",
        status: "UNKNOWN",
        detail: "请查看 readiness",
      },
      {
        id: "executor",
        label: "执行器",
        status: health ? "HEALTHY" : "UNKNOWN",
        detail: "请查看公开安全上下文",
      },
    ],
  };
}
