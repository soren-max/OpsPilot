export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
    status: ["auth", "status"] as const,
  },
  system: {
    health: ["system", "health"] as const,
    ready: ["system", "ready"] as const,
  },
  environments: ["environments"] as const,
  services: (environmentId: string) => ["services", environmentId] as const,
  serviceHosts: (serviceId: string) => ["service-hosts", serviceId] as const,
  hosts: (environmentId: string) => ["hosts", environmentId] as const,
  assets: (environmentId: string) => ["assets", environmentId] as const,
  hostServices: (hostId: string) => ["host-services", hostId] as const,
  tasks: ["tasks"] as const,
  operationRequests: ["operation-requests"] as const,
  task: (taskId: string | null) => ["task", taskId] as const,
  taskLogs: (taskId: string | undefined) => ["task-logs", taskId] as const,
  audits: ["audits"] as const,
  incidents: (environment: string) => ["incidents", environment] as const,
  incident: (incidentId: string | undefined) => ["incident", incidentId] as const,
  incidentTimeline: (incidentId: string | undefined) => ["incident-timeline", incidentId] as const,
  incidentWorkflows: (incidentId: string | undefined) =>
    ["incident-workflows", incidentId] as const,
  statusSnapshots: (environmentId: string) => ["status-snapshots", environmentId] as const,
};
