import type { Environment, Host, Service } from "../types";
import { api } from "./client";

export const catalogApi = {
  environments: () => api<Environment[]>("/environments"),
  services: (environmentId: string) =>
    api<Service[]>(`/services?environment_id=${encodeURIComponent(environmentId)}`),
  serviceHosts: (serviceId: string) => api<Host[]>(`/services/${serviceId}/hosts`),
  hosts: (environmentId: string) =>
    api<Host[]>(`/hosts?environment_id=${encodeURIComponent(environmentId)}`),
  hostServices: (hostId: string) => api<Service[]>(`/hosts/${hostId}/services`),
};
