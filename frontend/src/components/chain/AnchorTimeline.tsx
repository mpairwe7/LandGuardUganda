"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Anchor } from "lucide-react";
import { api } from "@/lib/api";
import { formatTs } from "@/lib/format";
import { HashDisplay } from "@/components/common/HashDisplay";
import { StatusPill } from "@/components/common/StatusPill";

interface AnchorListResponse {
  total: number;
  items: Array<{
    batch_id: string;
    district_id: number;
    root_hash: string;
    leaf_count: number;
    tx_hash: string | null;
    block_number: number | null;
    anchored_at: number;
    status: string;
  }>;
}

/**
 * Anchor explorer timeline. Each row is a batch; the gold "verified" pill
 * only fires once the chain has confirmed it.
 */
export function AnchorTimeline({ districtId }: { districtId?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["anchors", districtId ?? "all"],
    queryFn: () =>
      api.get<AnchorListResponse>(
        `/v1/anchors?limit=20${districtId != null ? `&district_id=${districtId}` : ""}`,
      ),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div className="card-surface animate-pulse">
        <p className="text-sm text-slate-500">Loading anchor batches…</p>
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="card-surface">
        <p className="text-sm text-slate-500">No anchor batches yet.</p>
      </div>
    );
  }

  return (
    <section className="card-surface">
      <header className="mb-3 flex items-center gap-2 border-b border-slate-200 pb-3">
        <Anchor className="size-4 text-guard-700" aria-hidden />
        <h2 className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Anchor timeline
        </h2>
      </header>
      <ol className="divide-y divide-slate-100" role="list">
        {data.items.map((a) => (
          <li
            key={a.batch_id}
            className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:grid sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-4"
          >
            <div className="min-w-0">
              <Link
                href={`/anchors/${a.batch_id}`}
                className="block text-sm text-slate-900 hover:underline"
              >
                <HashDisplay value={a.batch_id} head={8} tail={6} copy={false} />
              </Link>
              <p className="mt-0.5 text-xs text-slate-500">
                District {a.district_id} · {a.leaf_count} events ·{" "}
                {formatTs(a.anchored_at)}
              </p>
            </div>
            <div className="text-xs text-slate-600 sm:text-right">
              <HashDisplay value={a.tx_hash} head={6} tail={4} copy={false} />
              <p className="mt-0.5 tabular-nums">block {a.block_number ?? "—"}</p>
            </div>
            <div className="self-start sm:self-auto">
              <StatusPill kind={a.status === "CONFIRMED" ? "verified" : "pending"}>
                {a.status}
              </StatusPill>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
