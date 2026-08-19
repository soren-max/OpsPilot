import type { Environment, SecurityContext, SystemReady } from "../types";

export type OperationAction = "status" | "start" | "stop";

export type OperationCapabilityOutcome =
  | "EXECUTABLE"
  | "APPROVAL_REQUIRED"
  | "PERMISSION_DENIED"
  | "ENVIRONMENT_POLICY_DENIED"
  | "EXECUTOR_UNSUPPORTED"
  | "PROFILE_NOT_CONFIGURED"
  | "PRODUCTION_OPERATION_DENIED"
  | "UNAVAILABLE";

export interface OperationCapability {
  action: OperationAction;
  outcome: OperationCapabilityOutcome;
  canInitiate: boolean;
  requiresApproval: boolean;
  label: string;
  reason: string;
}

export type OperationCapabilities = Record<OperationAction, OperationCapability>;

interface CapabilityInput {
  security: SecurityContext;
  readiness?: SystemReady;
  readinessUnavailable?: boolean;
  environment?: Pick<Environment, "enabled" | "environment_level">;
}

const requiredPermission: Record<OperationAction, string> = {
  status: "service.status",
  start: "service.start",
  stop: "service.stop",
};

const labels: Record<OperationCapabilityOutcome, string> = {
  EXECUTABLE: "立即可执行",
  APPROVAL_REQUIRED: "需要审批",
  PERMISSION_DENIED: "无权限",
  ENVIRONMENT_POLICY_DENIED: "环境策略禁止",
  EXECUTOR_UNSUPPORTED: "Executor 不支持",
  PROFILE_NOT_CONFIGURED: "Profile 未配置",
  PRODUCTION_OPERATION_DENIED: "生产操作禁止",
  UNAVAILABLE: "能力状态不可用",
};

function result(
  action: OperationAction,
  outcome: OperationCapabilityOutcome,
  reason: string,
): OperationCapability {
  return {
    action,
    outcome,
    canInitiate: outcome === "EXECUTABLE" || outcome === "APPROVAL_REQUIRED",
    requiresApproval: outcome === "APPROVAL_REQUIRED",
    label: labels[outcome],
    reason,
  };
}

export function resolveOperationCapability(
  action: OperationAction,
  { security, readiness, readinessUnavailable = false, environment }: CapabilityInput,
): OperationCapability {
  const permissions = new Set(security.permissions);
  const permission = requiredPermission[action];
  if (!permissions.has(permission)) {
    return result(action, "PERMISSION_DENIED", `缺少权限 ${permission}。`);
  }
  if (
    action !== "status" &&
    security.approval_required_for_write &&
    !permissions.has("operation.create")
  ) {
    return result(action, "PERMISSION_DENIED", "缺少权限 operation.create，不能发起审批。");
  }
  if (environment && !environment.enabled) {
    return result(action, "ENVIRONMENT_POLICY_DENIED", "当前环境已停用。");
  }
  if (readinessUnavailable) {
    return result(action, "UNAVAILABLE", "无法读取 /ready，不能确认执行能力。");
  }
  if (readiness?.services.required) {
    if (readiness.status !== "ready") {
      const failed = Object.entries(readiness.services.preflight?.checks ?? {}).find(
        ([, check]) => check.status !== "ok",
      );
      const detail = failed ? `：${failed[0]} - ${failed[1].reason}` : "";
      return result(action, "UNAVAILABLE", `真实执行预检未通过${detail}。`);
    }
    const profileStatus = readiness.services.command_profile;
    if (profileStatus !== "configured") {
      const detail = readiness.services.profile_error
        ? `：${readiness.services.profile_error}`
        : "";
      return result(
        action,
        "PROFILE_NOT_CONFIGURED",
        `Command Profile ${readiness.services.profile_name || "pending-confirmation"} 未就绪${detail}。`,
      );
    }
    if (!readiness.services.capabilities.includes(action)) {
      return result(
        action,
        "EXECUTOR_UNSUPPORTED",
        `当前 Command Profile 未声明 ${action} capability。`,
      );
    }
  }
  if (!security.executor_capabilities[action]) {
    return result(action, "EXECUTOR_UNSUPPORTED", `当前 Executor 未声明 ${action} capability。`);
  }
  if (action !== "status" && !security.write_operations) {
    return result(action, "ENVIRONMENT_POLICY_DENIED", "当前环境未启用写操作。");
  }
  if (
    environment?.environment_level === "PRODUCTION" &&
    action !== "status" &&
    !security.production_operations
  ) {
    return result(action, "PRODUCTION_OPERATION_DENIED", "生产环境写操作未启用。");
  }
  if (!security.allowed_actions.includes(action)) {
    return result(action, "ENVIRONMENT_POLICY_DENIED", `${action} 不在后端返回的有效动作集合中。`);
  }
  if (action !== "status" && security.approval_required_for_write) {
    const selfApproval = security.approval.allow_self_approval && security.approval.can_approve;
    return result(
      action,
      "APPROVAL_REQUIRED",
      selfApproval
        ? `需要 ${security.approval.minimum_approvers} 名审批人；当前账号可按策略自审批。`
        : `需要 ${security.approval.minimum_approvers} 名审批人，提交后进入待审批状态。`,
    );
  }
  return result(
    action,
    "EXECUTABLE",
    "权限、环境策略、Executor 和 Profile capability 均已通过。按下操作后将立即创建任务。",
  );
}

export function resolveOperationCapabilities(input: CapabilityInput): OperationCapabilities {
  return {
    status: resolveOperationCapability("status", input),
    start: resolveOperationCapability("start", input),
    stop: resolveOperationCapability("stop", input),
  };
}
