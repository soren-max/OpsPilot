import type {
  CredentialMetadata,
  IntegrationConfig,
  IntegrationConfigInput,
  IntegrationTestResult,
} from "../types";
import { api } from "./client";

const root = "/admin/operations-integration";

export const integrationApi = {
  list: () => api<IntegrationConfig[]>(root),
  create: (body: IntegrationConfigInput) =>
    api<IntegrationConfig>(root, { method: "POST", body: JSON.stringify(body) }),
  get: (environmentId: string) => api<IntegrationConfig>(`${root}/${environmentId}`),
  save: (environmentId: string, body: IntegrationConfigInput) =>
    api<IntegrationConfig>(`${root}/${environmentId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  validate: (environmentId: string) =>
    api<IntegrationConfig>(`${root}/${environmentId}/validate`, { method: "POST" }),
  testSsh: (environmentId: string, hostId: string) =>
    api<IntegrationTestResult>(`${root}/${environmentId}/test-ssh/${hostId}`, {
      method: "POST",
    }),
  testStatus: (environmentId: string, hostId: string, serviceId: string) =>
    api<IntegrationTestResult>(`${root}/${environmentId}/test-status/${hostId}/${serviceId}`, {
      method: "POST",
    }),
  enable: (environmentId: string) =>
    api<IntegrationConfig>(`${root}/${environmentId}/enable`, { method: "POST" }),
  disable: (environmentId: string) =>
    api<IntegrationConfig>(`${root}/${environmentId}/disable`, { method: "POST" }),
  credentials: () => api<CredentialMetadata[]>(`${root}/credentials`),
  createCredential: (name: string, privateKey: string) =>
    api<CredentialMetadata>(`${root}/credentials`, {
      method: "POST",
      body: JSON.stringify({ name, private_key: privateKey }),
    }),
};
