// Runtime fetch of the backend /readyz, exposed to the browser without
// having to widen the /api/proxy/[...path] proxy (which only forwards
// /api/v1/*). Used by ChainStatusBeacon to drive the "Chain live /
// queued / down" pill in the global header.

import { NextResponse } from "next/server";

const DEFAULT_BACKEND =
  "https://landguard-backend-d1e66f33.renu-01.cranecloud.io";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const backend = process.env.BACKEND_URL || DEFAULT_BACKEND;
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
