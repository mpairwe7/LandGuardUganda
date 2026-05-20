"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useChainStatusStore } from "@/store/useChainStatusStore";

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
      const resp = await fetch("/api/proxy/../readyz");
      // Same-origin proxy doesn't expose /readyz directly; fall back:
      try {
        const r = await fetch("/api/health");
        if (r.ok) return (await r.json()) as Readyz;
      } catch {}
      return { ok: false, details: {} } as Readyz;
    },
    refetchInterval: 5_000,
  });

  useEffect(() => {
    if (data?.details?.anchor_breaker) {
      setBreaker(data.details.anchor_breaker as never);
    }
  }, [data, setBreaker]);

  const breakerOpen = data?.details.anchor_breaker === "open";
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
