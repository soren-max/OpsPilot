import type { OperationRequest, ServiceStatusSnapshot, Task, TaskLog } from "../types";
import { api } from "./client";

function idempotencyKey(action: string): string {
  const suffix = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  return `web:${action}:${suffix}`;
}

export const tasksApi = {
  list: () => api<Task[]>("/tasks"),
  detail: (taskId: string) => api<Task>(`/tasks/${taskId}`),
  logs: (taskId: string) => api<TaskLog[]>(`/tasks/${taskId}/logs`),
  statusSnapshots: (environmentId: string) =>
    api<ServiceStatusSnapshot[]>(
      `/status-snapshots?environment_id=${encodeURIComponent(environmentId)}`,
    ),
  createOperation: (
    environmentId: string,
    serviceId: string,
    hostIds: string[],
    action: "status" | "start" | "stop",
  ) =>
    api<{ task_id: string; status: Task["status"] }>("/operations", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey(action) },
      body: JSON.stringify({
        environment_id: environmentId,
        action,
        scope: "service_hosts",
        service_id: serviceId,
        host_ids: hostIds,
        requested_by: "web-user",
        parameters: {},
      }),
    }),
  createOperationRequest: (
    environmentId: string,
    serviceId: string,
    hostIds: string[],
    action: "start" | "stop",
  ) =>
    api<OperationRequest>("/operation-requests", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey(action) },
      body: JSON.stringify({
        operation: {
          environment_id: environmentId,
          action,
          scope: "service_hosts",
          service_id: serviceId,
          host_ids: hostIds,
          requested_by: "web-user",
          parameters: {},
        },
        reason: `Web console ${action} request`,
      }),
    }),
  approveOperationRequest: (requestId: string) =>
    api<OperationRequest>(`/operation-requests/${requestId}/approve`, {
      method: "POST",
      body: JSON.stringify({ comment: "TEST self-approval from web console" }),
    }),
  operationRequests: () => api<OperationRequest[]>("/operation-requests"),
  rejectOperationRequest: (requestId: string) =>
    api<OperationRequest>(`/operation-requests/${requestId}/reject`, {
      method: "POST",
      body: JSON.stringify({ comment: "Rejected from web console" }),
    }),
  cancelOperationRequest: (requestId: string) =>
    api<OperationRequest>(`/operation-requests/${requestId}/cancel`, { method: "POST" }),
  cancel: (taskId: string) => api<Task>(`/tasks/${taskId}/cancel`, { method: "POST" }),
};
