import type { SystemHealth, SystemReady } from "../types";
import { api } from "./client";

export const systemApi = {
  health: () => api<SystemHealth>("/health"),
  ready: () => api<SystemReady>("/ready"),
};
