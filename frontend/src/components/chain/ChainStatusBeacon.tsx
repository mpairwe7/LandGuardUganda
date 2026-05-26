"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useChainStatusStore } from "@/store/useChainStatusStore";

// When NEXT_PUBLIC_BACKEND_URL is baked in at build time, the browser
// fetches /readyz directly against the backend's public ingress (with
// CORS). Otherwise we use the server-side helper at /api/chain-status,
// which only works in environments where the frontend pod has outbound
// internet (local dev, Docker compose).
const PUBLIC_BACKEND = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "").replace(/\/$/, "");
const READYZ_URL = PUBLIC_BACKEND ? `${PUBLIC_BACKEND}/readyz` : "/api/chain-status";

interface Readyz {
  ok: boolean;
  degraded?: boolean;
  details: {
    db?: string;
    redis?: string;
    blockchain?: { ok?: boolean; block?: number } | string;
    anchor_breaker?: string;
  };
}

export function ChainStatusBeacon() {
  const setBreaker = useChainStatusStore((s) => s.setBreaker);
  const { data } = useQuery({
    queryKey: ["chainStatus"],
    queryFn: async () => {
      try {
        const r = await fetch(READYZ_URL, { cache: "no-store" });
        if (r.ok) return (await r.json()) as Readyz;
      } catch {
        /* fall through */
      }
      return { ok: false, details: {} } as Readyz;
    },
    refetchInterval: 5_000,
    retry: false,
  });

  useEffect(() => {
    if (data?.details?.anchor_breaker) {
      setBreaker(data.details.anchor_breaker as never);
    }
  }, [data, setBreaker]);

  const breakerOpen = data?.details?.anchor_breaker === "open";
  const status = !data?.ok ? "down" : breakerOpen ? "queued" : "live";
  const color =
    status === "down"
      ? "bg-status-frozen"
      : status === "queued"
        ? "bg-status-pending"
        : "bg-status-verified";
  const label =
    status === "down" ? "System down" : status === "queued" ? "Chain queued" : "Chain live";

  return (
    <span
      className="inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-current/80"
      role="status"
      aria-label={`Chain status: ${label}`}
    >
      <span
        className={`inline-block size-2 rounded-full ${color} ${status === "queued" ? "animate-pulse" : ""}`}
        aria-hidden
      />
      <span>{label}</span>
    </span>
  );
}
