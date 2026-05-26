// Resolves a working backend URL. In Crane Cloud, pods can't always reach
// the public ingress for a sibling app — egress→public ingress is allowed
// in some clusters and blocked in others, and the cluster's internal DNS
// for sibling-service hostnames isn't documented for tenants.
//
// Strategy: try a small ordered list of candidates on first use, cache
// the winner for the lifetime of the process, and surface a clear error
// when none work. Each candidate has a short timeout so the worst case
// is ~3s, not 30s.

const CANDIDATES_FROM_ENV = (process.env.BACKEND_URL_CANDIDATES ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const FALLBACK_CANDIDATES = [
  process.env.BACKEND_URL,
  "http://landguard-backend:8000",
  "http://landguard-backend",
  "https://landguard-backend-d1e66f33.renu-01.cranecloud.io",
].filter(Boolean) as string[];

const CANDIDATES = CANDIDATES_FROM_ENV.length ? CANDIDATES_FROM_ENV : FALLBACK_CANDIDATES;

let cached: string | null = null;
let resolving: Promise<string | null> | null = null;

async function probe(url: string): Promise<boolean> {
  try {
    const res = await fetch(`${url.replace(/\/$/, "")}/healthz`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function resolveBackendUrl(): Promise<string | null> {
  if (cached) return cached;
  if (resolving) return resolving;
  resolving = (async () => {
    for (const candidate of CANDIDATES) {
      if (await probe(candidate)) {
        cached = candidate;
        return candidate;
      }
    }
    return null;
  })();
  const result = await resolving;
  resolving = null;
  return result;
}

export function invalidateBackendUrl() {
  cached = null;
}

export function listCandidates() {
  return [...CANDIDATES];
}
