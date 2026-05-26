// Diagnostic endpoint. Enumerates the candidate backend URLs and also
// probes a few well-known external URLs so we can tell whether the
// frontend pod has *any* egress at all.

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

async function probe(url: string, healthPath = "/healthz"): Promise<Probe> {
  const start = Date.now();
  const target = healthPath === "" ? url : `${url.replace(/\/$/, "")}${healthPath}`;
  try {
    const res = await fetch(target, {
      cache: "no-store",
      signal: AbortSignal.timeout(3500),
    });
    return { url: target, ok: res.ok, status: res.status, ms: Date.now() - start };
  } catch (err) {
    return {
      url: target,
      ok: false,
      ms: Date.now() - start,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

// Candidate Kubernetes service-name forms. Project IDs/namespaces are
// not documented for tenants, so we try a few common patterns. The
// known Crane Cloud project for this deploy is "LandGuardUganda"
// (project_id 12087f2a-... from bootstrap); namespaces in Crane Cloud
// usually take the form `<project-name-slug>` lowercase.
const EXTRA_INTERNAL_CANDIDATES = [
  "http://landguard-backend.landguardgu.svc.cluster.local:8000",
  "http://landguard-backend.landguarduganda.svc.cluster.local:8000",
  "http://landguard-backend.default.svc.cluster.local:8000",
  "http://landguard-backend.svc.cluster.local:8000",
];

const EGRESS_CHECKS = [
  { url: "https://api.cranecloud.io/", healthPath: "" }, // egress to Crane Cloud API
  { url: "https://1.1.1.1/", healthPath: "" }, // Cloudflare DNS, generic egress test
  { url: "https://www.google.com/", healthPath: "" },
];

export async function GET() {
  const known = listCandidates();
  const all = [...known, ...EXTRA_INTERNAL_CANDIDATES];
  const probes = await Promise.all(all.map((url) => probe(url, "/healthz")));
  const egress = await Promise.all(EGRESS_CHECKS.map((c) => probe(c.url, c.healthPath)));
  return NextResponse.json(
    {
      env_backend_url: process.env.BACKEND_URL ?? null,
      env_candidates: process.env.BACKEND_URL_CANDIDATES ?? null,
      hostname: process.env.HOSTNAME ?? null,
      // Anything we can learn about the pod's networking
      probes,
      egress,
      first_working: probes.find((p) => p.ok)?.url ?? null,
    },
    { status: 200 },
  );
}
