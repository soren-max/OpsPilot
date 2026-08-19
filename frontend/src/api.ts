import { auditsApi } from "./api/audits";
import { authApi } from "./api/auth";
import { catalogApi } from "./api/catalog";
import { incidentsApi } from "./api/incidents";
import { tasksApi } from "./api/tasks";

export { ApiError, TOKEN_KEY } from "./api/client";
export { auditsApi } from "./api/audits";
export { authApi } from "./api/auth";
export { catalogApi } from "./api/catalog";
export { incidentsApi } from "./api/incidents";
export { systemApi } from "./api/system";
export { tasksApi } from "./api/tasks";

/** Compatibility facade while pages migrate to domain API modules. */
export const opsApi = {
  environments: catalogApi.environments,
  services: catalogApi.services,
  serviceHosts: catalogApi.serviceHosts,
  hosts: catalogApi.hosts,
  hostServices: catalogApi.hostServices,
  tasks: tasksApi.list,
  task: tasksApi.detail,
  taskLogs: tasksApi.logs,
  audits: auditsApi.list,
  incidents: incidentsApi.list,
  createOperation: tasksApi.createOperation,
  createStatusTask: (environmentId: string, serviceId: string, hostIds: string[]) =>
    tasksApi.createOperation(environmentId, serviceId, hostIds, "status"),
  login: authApi.login,
  logout: authApi.logout,
  me: authApi.me,
  authStatus: authApi.status,
};
