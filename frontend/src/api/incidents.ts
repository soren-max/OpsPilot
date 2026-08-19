import type { Incident, IncidentPage, TimelineItem } from "../types";
import { api } from "./client";

export const incidentsApi = {
  list: (environment: string) =>
    api<IncidentPage>(`/incidents?environment=${encodeURIComponent(environment)}&limit=100`),
  detail: (incidentId: string) => api<Incident>(`/incidents/${incidentId}`),
  timeline: (incidentId: string) => api<TimelineItem[]>(`/incidents/${incidentId}/timeline`),
};
