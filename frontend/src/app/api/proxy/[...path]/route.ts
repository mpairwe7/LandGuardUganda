// Runtime proxy: forwards /api/proxy/* → <BACKEND_URL>/api/*
//
// Why this exists as a route handler instead of `next.config.mjs` rewrites:
// Next.js evaluates rewrites at build time, so the target URL is baked into
// the standalone bundle. In our deploy topology (Crane Cloud), the backend's
// public URL isn't known when CI runs `next build`. A route handler reads
// `process.env.BACKEND_URL` at request time, so the target can be set via
// the frontend app's env_vars in the platform dashboard — or fall back to
// the deployed RENU URL when no env is present.

import { NextRequest, NextResponse } from "next/server";

const DEFAULT_BACKEND =
  "https://landguard-backend-d1e66f33.renu-01.cranecloud.io";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const backend = process.env.BACKEND_URL || DEFAULT_BACKEND;
  const { path } = await ctx.params;
  const subpath = Array.isArray(path) ? path.join("/") : "";
  const search = req.nextUrl.search ?? "";
  const target = `${backend.replace(/\/$/, "")}/api/${subpath}${search}`;

  const headers = new Headers(req.headers);
  // Strip hop-by-hop and the inbound host so the upstream resolves correctly.
  headers.delete("host");
  headers.delete("content-length");
  headers.delete("connection");

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
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
