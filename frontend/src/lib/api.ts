// Same-origin proxy: /api/proxy/* → backend /api/*  (configured in next.config.mjs)

import { useAuthStore } from "@/store/useAuthStore";

const BASE = "/api/proxy";

export type ApiError = { status: number; detail: string; requestId?: string };

async function request<T>(
  path: string,
  init: RequestInit & { json?: unknown; idempotencyKey?: string } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.json !== undefined) headers.set("Content-Type", "application/json");

  const auth = useAuthStore.getState();
  if (auth.token) headers.set("Authorization", `Bearer ${auth.token}`);
  if (auth.demoRole) headers.set("X-Demo-Role", auth.demoRole);
  if (auth.demoDistrictId != null) headers.set("X-Demo-District", String(auth.demoDistrictId));
  if (init.idempotencyKey) headers.set("Idempotency-Key", init.idempotencyKey);

  const url = `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const resp = await fetch(url, {
    ...init,
    headers,
    body: init.json !== undefined ? JSON.stringify(init.json) : init.body,
  });

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    const err: ApiError = {
      status: resp.status,
      detail,
      requestId: resp.headers.get("X-Request-Id") ?? undefined,
    };
    throw err;
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, json?: unknown, idempotencyKey?: string) =>
    request<T>(path, { method: "POST", json, idempotencyKey }),
  put: <T>(path: string, json?: unknown, idempotencyKey?: string) =>
    request<T>(path, { method: "PUT", json, idempotencyKey }),
  patch: <T>(path: string, json?: unknown, idempotencyKey?: string) =>
    request<T>(path, { method: "PATCH", json, idempotencyKey }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export function makeIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
