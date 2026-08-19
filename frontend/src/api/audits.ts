import type { Audit } from "../types";
import { api } from "./client";

export const auditsApi = {
  list: () => api<Audit[]>("/audits"),
};
