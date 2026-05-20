"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatTs } from "@/lib/format";
import { StatusPill } from "@/components/common/StatusPill";

interface AnchorListResponse {
  total: number;
  items: Array<{
    batch_id: string;
    district_id: number;
    root_hash: string;
    tx_hash: string | null;
    anchored_at: number;
    leaf_count: number;
    status: string;
  }>;
}

/**
 * "Latest anchor" headline — the public landing's proof-of-life. Streams in
 * via Suspense from the backend, then settles into a verified pill.
 */
export function LatestAnchorBadge() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["anchors", "recent"],
    queryFn: () => api.get<AnchorListResponse>("/v1/anchors?limit=1"),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return <StatusPill kind="pending">Loading chain state…</StatusPill>;
  }
  if (isError || !data || data.items.length === 0) {
    return <StatusPill kind="neutral">Awaiting first anchor</StatusPill>;
  }
  const a = data.items[0]!;
  return (
    <StatusPill kind="verified">
      Block anchored · {formatTs(a.anchored_at)}
    </StatusPill>
  );
}
