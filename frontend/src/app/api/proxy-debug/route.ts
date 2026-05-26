// Diagnostic endpoint: probes every backend candidate and reports
// reachability. Use this from outside the pod to learn which URL form
// the cluster actually permits.
//
//   curl https://<frontend>/api/proxy-debug | jq .

import { NextResponse } from "next/server";
import { listCandidates } from "@/lib/backendUrl";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

interface Probe {
  url: string;
  ok: boolean;
  status?: number;
  ms: number;
  error?: string;
}

async function probe(url: string): Promise<Probe> {
  const start = Date.now();
  try {
    const res = await fetch(`${url.replace(/\/$/, "")}/healthz`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3500),
    });
    return { url, ok: res.ok, status: res.status, ms: Date.now() - start };
  } catch (err) {
    return {
      url,
      ok: false,
      ms: Date.now() - start,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function GET() {
  const candidates = listCandidates();
  const probes = await Promise.all(candidates.map(probe));
  return NextResponse.json(
    {
      env_backend_url: process.env.BACKEND_URL ?? null,
      env_candidates: process.env.BACKEND_URL_CANDIDATES ?? null,
      probes,
      first_working: probes.find((p) => p.ok)?.url ?? null,
    },
    { status: 200 },
  );
}
