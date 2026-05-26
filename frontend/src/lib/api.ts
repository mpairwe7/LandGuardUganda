// Backend base URL strategy:
//
// In production (Crane Cloud), the frontend pod has no outbound egress
// — it cannot reach the backend's public URL from within the pod, so
// the `/api/proxy/*` route handler can't function. Instead the browser
// talks to the backend directly over CORS. `NEXT_PUBLIC_BACKEND_URL`
// is baked into the client bundle at build time (frontend/Dockerfile)
// and points at the backend's public ingress.
//
// In local dev (`bun dev` / `bun start`) without that env var set, we
// fall back to `/api/proxy` and let the runtime route handler at
// `src/app/api/proxy/[...path]/route.ts` reach a backend running on
// localhost or a sibling container.

import { useAuthStore } from "@/store/useAuthStore";

const PUBLIC_BACKEND = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "").replace(/\/$/, "");
const BASE = PUBLIC_BACKEND ? `${PUBLIC_BACKEND}/api` : "/api/proxy";

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
