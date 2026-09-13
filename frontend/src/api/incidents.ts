import type {
  AgentEvent,
  Incident,
  IncidentPage,
  ExecutionRecord,
  RetrievedKnowledge,
  IncidentReplay,
  TimelineItem,
  WorkflowRun,
} from "../types";
import { api } from "./client";
import { streamSse } from "./sse";

export const incidentsApi = {
  list: (environment: string) =>
    api<IncidentPage>(`/incidents?environment=${encodeURIComponent(environment)}&limit=100`),
  detail: (incidentId: string) => api<Incident>(`/incidents/${incidentId}`),
  timeline: (incidentId: string) => api<AgentEvent[]>(`/incidents/${incidentId}/events`),
  auditTimeline: (incidentId: string) => api<TimelineItem[]>(`/incidents/${incidentId}/timeline`),
  streamEvents: (
    incidentId: string,
    onEvent: (event: AgentEvent, eventId: string | undefined) => void,
    options: { signal: AbortSignal; lastEventId?: string },
  ) => streamSse(`/incidents/${incidentId}/events/stream`, onEvent, options),
  replay: (incidentId: string, withHistoricalMemory = true) =>
    api<IncidentReplay>(`/incidents/${incidentId}/replay`, {
      method: "POST",
      body: JSON.stringify({
        investigator_mode: "deterministic",
        with_historical_memory: withHistoricalMemory,
      }),
    }),
  workflows: (incidentId: string) => api<WorkflowRun[]>(`/incidents/${incidentId}/workflows`),
  related: (incidentId: string) => api<RetrievedKnowledge[]>(`/incidents/${incidentId}/related`),
  executions: (incidentId?: string) =>
    api<ExecutionRecord[]>(
      incidentId ? `/executions?incident_id=${encodeURIComponent(incidentId)}` : "/executions",
    ),
};
