import type {
  Incident,
  IncidentPage,
  ExecutionRecord,
  RetrievedKnowledge,
  TimelineItem,
  WorkflowRun,
} from "../types";
import { api } from "./client";

export const incidentsApi = {
  list: (environment: string) =>
    api<IncidentPage>(`/incidents?environment=${encodeURIComponent(environment)}&limit=100`),
  detail: (incidentId: string) => api<Incident>(`/incidents/${incidentId}`),
  timeline: (incidentId: string) => api<TimelineItem[]>(`/incidents/${incidentId}/timeline`),
  workflows: (incidentId: string) => api<WorkflowRun[]>(`/incidents/${incidentId}/workflows`),
  related: (incidentId: string) => api<RetrievedKnowledge[]>(`/incidents/${incidentId}/related`),
  executions: (incidentId?: string) =>
    api<ExecutionRecord[]>(
      incidentId ? `/executions?incident_id=${encodeURIComponent(incidentId)}` : "/executions",
    ),
};
