import type { ApiEnvelope } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
export const TOKEN_KEY = "opspilot_token";

type ApiErrorBody = { code?: string; message?: string; request_id?: string };
type EnvelopeError = { error?: ApiErrorBody; request_id?: string };

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly requestId?: string,
    public readonly code?: string,
    public readonly status?: number,
    public readonly serviceUnavailable = false,
  ) {
    super(message);
  }
}

function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage can be unavailable in hardened browsers; authentication still fails closed.
  }
}

async function readResponse(response: Response): Promise<unknown | null> {
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  const text = await response.text();
  if (!text.trim()) return null;
  if (contentType.includes("application/json")) {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      if (import.meta.env.DEV) {
        console.warn("OPSPILOT API returned malformed JSON", { status: response.status, contentType });
      }
      return null;
    }
  }
  if (import.meta.env.DEV) {
    console.warn("OPSPILOT API returned a non-JSON response", {
      status: response.status,
      contentType,
      hasBody: true,
    });
  }
  return null;
}

function asErrorBody(body: unknown): ApiErrorBody {
  if (!body || typeof body !== "object") return {};
  const direct = body as ApiErrorBody & EnvelopeError;
  return direct.error ? { ...direct.error, request_id: direct.request_id } : direct;
}

interface ApiOptions {
  envelope?: boolean;
  redirectOnAuthFailure?: boolean;
}

export async function request<T>(
  path: string,
  init?: RequestInit,
  options: ApiOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { ...headers, ...init?.headers },
    });
  } catch {
    throw new ApiError("服务暂时不可用，请稍后重试。", undefined, "NETWORK_ERROR", undefined, true);
  }
  const body = await readResponse(response);
  const error = asErrorBody(body);
  if (!response.ok) {
    const serviceUnavailable = body === null || response.status >= 500;
    const message = serviceUnavailable
      ? "服务暂时不可用，请稍后重试。"
      : error.message || "请求暂时无法完成，请稍后重试。";
    if (response.status === 401 && options.redirectOnAuthFailure !== false) {
      clearToken();
      window.location.assign("/login");
    }
    throw new ApiError(message, error.request_id, error.code, response.status, serviceUnavailable);
  }
  if (body === null) {
    throw new ApiError(
      "服务暂时不可用，请稍后重试。",
      undefined,
      "EMPTY_RESPONSE",
      response.status,
      true,
    );
  }
  if (options.envelope === false) return body as T;
  const envelope = body as ApiEnvelope<T>;
  if (!("data" in envelope)) {
    throw new ApiError(
      "服务返回了无法识别的数据。",
      error.request_id,
      "INVALID_RESPONSE",
      response.status,
      true,
    );
  }
  return envelope.data;
}

export const api = <T>(path: string, init?: RequestInit) => request<T>(path, init);
export const publicApi = <T>(path: string, init?: RequestInit) =>
  request<T>(path, init, { redirectOnAuthFailure: false });
