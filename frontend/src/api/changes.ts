import type { ChangePage, ChangePreview, ChangeRecord, ChangeTimelineItem } from "../types";
import { api } from "./client";

export const changesApi = {
  list: (incidentId?: string) =>
    api<ChangePage>(
      incidentId ? `/changes?incident_id=${encodeURIComponent(incidentId)}` : "/changes?limit=100",
    ),
  detail: (changeId: string) => api<ChangeRecord>(`/changes/${changeId}`),
  timeline: (changeId: string) => api<ChangeTimelineItem[]>(`/changes/${changeId}/timeline`),
  preview: (changeId: string) => api<ChangePreview>(`/changes/${changeId}/preview`),
  prepare: (changeId: string) =>
    api<ChangeRecord>(`/changes/${changeId}/prepare`, { method: "POST" }),
  approve: (changeId: string, reason: string, planFingerprint: string) =>
    api<ChangeRecord>(`/changes/${changeId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason, plan_fingerprint: planFingerprint }),
    }),
  reject: (changeId: string, reason: string) =>
    api<ChangeRecord>(`/changes/${changeId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  reconcile: (changeId: string) =>
    api<ChangeRecord>(`/changes/${changeId}/reconcile`, { method: "POST" }),
};
