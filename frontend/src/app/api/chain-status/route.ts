// Runtime fetch of the backend /readyz, exposed to the browser without
// having to widen the /api/proxy/[...path] proxy (which only forwards
// /api/v1/*). Used by ChainStatusBeacon to drive the "Chain live /
// queued / down" pill in the global header.

import { NextResponse } from "next/server";
import { resolveBackendUrl } from "@/lib/backendUrl";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const backend = await resolveBackendUrl();
  if (!backend) {
    return NextResponse.json(
      { ok: false, details: {}, error: "no_reachable_backend" },
      { status: 200 },
    );
  }
  try {
    const upstream = await fetch(`${backend.replace(/\/$/, "")}/readyz`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (!upstream.ok) {
      return NextResponse.json(
        { ok: false, details: {}, upstream_status: upstream.status },
        { status: 200 },
      );
    }
    const body = await upstream.json();
    return NextResponse.json(body, { status: 200 });
  } catch (err) {
    return NextResponse.json(
      {
        ok: false,
        details: {},
        error: err instanceof Error ? err.message : String(err),
      },
      { status: 200 },
    );
  }
}
