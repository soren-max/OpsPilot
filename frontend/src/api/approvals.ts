import type { ApprovalRequest } from "../types";
import { api } from "./client";

export const approvalsApi = {
  list: (incidentId?: string) =>
    api<ApprovalRequest[]>(
      incidentId ? `/approvals?incident_id=${encodeURIComponent(incidentId)}` : "/approvals",
    ),
  approve: (approvalId: string, reason: string) =>
    api<ApprovalRequest>(`/approvals/${approvalId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  reject: (approvalId: string, reason: string) =>
    api<ApprovalRequest>(`/approvals/${approvalId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
};
