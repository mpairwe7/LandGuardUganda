// Runtime proxy: forwards /api/proxy/* → <backend>/api/*
//
// Why this exists as a route handler instead of `next.config.mjs` rewrites:
// Next.js evaluates rewrites at build time, so the target URL is baked
// into the standalone bundle. In our deploy topology (Crane Cloud), the
// backend's reachable URL from inside the frontend pod isn't known when
// CI runs `next build`. A route handler probes candidates at request
// time — see `frontend/src/lib/backendUrl.ts`.

import { NextRequest, NextResponse } from "next/server";
import { resolveBackendUrl, invalidateBackendUrl, listCandidates } from "@/lib/backendUrl";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const backend = await resolveBackendUrl();
  if (!backend) {
    return NextResponse.json(
      {
        ok: false,
        error: "no_reachable_backend",
        candidates: listCandidates(),
      },
      { status: 502 },
    );
  }

  const { path } = await ctx.params;
  const subpath = Array.isArray(path) ? path.join("/") : "";
  const search = req.nextUrl.search ?? "";
  const target = `${backend.replace(/\/$/, "")}/api/${subpath}${search}`;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
    signal: AbortSignal.timeout(15_000),
  };
  if (!["GET", "HEAD"].includes(req.method)) {
    init.body = await req.arrayBuffer();
  }

  try {
    const upstream = await fetch(target, init);
    const respHeaders = new Headers(upstream.headers);
    respHeaders.delete("content-encoding");
    respHeaders.delete("transfer-encoding");
    return new NextResponse(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  } catch (err) {
    // If the cached URL stopped working, invalidate so the next request
    // re-probes.
    invalidateBackendUrl();
    return NextResponse.json(
      {
        ok: false,
        error: "upstream_unreachable",
        backend,
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 502 },
    );
  }
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
export const HEAD = forward;
export const OPTIONS = forward;
