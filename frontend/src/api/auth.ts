import type { AuthUser, LoginResponse, SecurityContext } from "../types";
import { api, publicApi, request } from "./client";

export const authApi = {
  login: (username: string, password: string) =>
    request<LoginResponse>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ username, password }) },
      { envelope: false, redirectOnAuthFailure: false },
    ),
  logout: () => api<{ message: string }>("/auth/logout", { method: "POST" }),
  me: () => request<AuthUser>("/auth/me", undefined, { envelope: false }),
  status: () => publicApi<SecurityContext>("/auth/status"),
};
