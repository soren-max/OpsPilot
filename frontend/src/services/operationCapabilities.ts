import type { Environment, SecurityContext, SystemReady } from "../types";

export type OperationAction = "status" | "restart";
export type OperationCapabilityOutcome =
  | "EXECUTABLE"
  | "APPROVAL_REQUIRED"
  | "PERMISSION_DENIED"
  | "ENVIRONMENT_POLICY_DENIED"
  | "BACKEND_UNAVAILABLE"
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

const labels: Record<OperationCapabilityOutcome, string> = {
  EXECUTABLE: "立即可执行",
  APPROVAL_REQUIRED: "需要审批",
  PERMISSION_DENIED: "无权限",
  ENVIRONMENT_POLICY_DENIED: "环境策略禁止",
  BACKEND_UNAVAILABLE: "执行后端不可用",
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
  const capability = action === "status" ? "observe" : "remediate";
  if (!security.capabilities[capability]) {
    return result(action, "PERMISSION_DENIED", `当前账号没有 ${capability} 能力。`);
  }
  if (environment && !environment.enabled) {
    return result(action, "ENVIRONMENT_POLICY_DENIED", "当前环境已停用。");
  }
  if (readinessUnavailable) {
    return result(action, "UNAVAILABLE", "无法读取 /ready，不能确认执行能力。");
  }
  if (readiness && !readiness.execution_backend.available) {
    return result(action, "BACKEND_UNAVAILABLE", "执行后端当前不可用。");
  }
  if (action === "restart" && !security.write_operations) {
    return result(action, "ENVIRONMENT_POLICY_DENIED", "当前环境未启用受控修复。 ");
  }
  if (
    action === "restart" &&
    environment?.environment_level === "PRODUCTION" &&
    !security.production_operations
  ) {
    return result(action, "PRODUCTION_OPERATION_DENIED", "生产环境修复未启用。");
  }
  if (action === "restart" && security.approval_required_for_write) {
    return result(action, "APPROVAL_REQUIRED", "重启是有状态修复，必须经过审批。");
  }
  return result(action, "EXECUTABLE", "结构化动作、权限、策略和执行后端均已通过。");
}

export function resolveOperationCapabilities(input: CapabilityInput): OperationCapabilities {
  return {
    status: resolveOperationCapability("status", input),
    restart: resolveOperationCapability("restart", input),
  };
}
