"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { formatTs } from "@/lib/format";
import { HashDisplay } from "@/components/common/HashDisplay";
import { StatusPill, type StatusKind } from "@/components/common/StatusPill";

interface AnchorRecord {
  batch_id: string;
  district_id: number;
  root_hash: string;
  first_seq: number;
  last_seq: number;
  leaf_count: number;
  tx_hash: string | null;
  block_number: number | null;
  anchored_at: number;
  confirmed_at: number | null;
  status: string;
}

const STATUS_KIND: Record<string, StatusKind> = {
  CONFIRMED: "verified",
  ANCHORED: "verified",
  PENDING: "pending",
  FAILED: "frozen",
};

export default function AnchorDetailPage() {
  const params = useParams<{ batchId: string }>();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["anchors", params.batchId],
    queryFn: () => api.get<AnchorRecord>(`/v1/anchors/${params.batchId}`),
    staleTime: Infinity,
  });

  if (isLoading) {
    return (
      <p className="mx-auto max-w-citizen text-sm text-slate-500">
        Loading anchor batch…
      </p>
    );
  }
  if (isError || !data) {
    return (
      <div className="mx-auto max-w-citizen">
        <div className="card-surface state-frozen flex items-start gap-3">
          <ShieldAlert
            className="size-5 shrink-0 text-status-frozen"
            aria-hidden
          />
          <p className="text-sm text-slate-700">Batch not found.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-citizen space-y-6">
      <header className="space-y-2 border-b border-slate-200 pb-4">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Anchor batch
        </p>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="font-mono text-xl font-semibold text-slate-900">
            {data.batch_id}
          </h1>
          <StatusPill kind={STATUS_KIND[data.status] ?? "neutral"}>
            {data.status}
          </StatusPill>
        </div>
      </header>

      <section className="card-surface">
        <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
          <Field label="District">
            <span className="font-mono text-slate-900 tabular-nums">
              {data.district_id}
            </span>
          </Field>
          <Field label="Events anchored">
            <span className="text-slate-900 tabular-nums">
              {data.leaf_count.toLocaleString()}{" "}
              <span className="text-slate-500">
                (seq {data.first_seq.toLocaleString()}–
                {data.last_seq.toLocaleString()})
              </span>
            </span>
          </Field>
          <Field label="Merkle root">
            <HashDisplay value={data.root_hash} head={14} tail={10} />
          </Field>
          <Field label="Anchored at">
            <span className="text-slate-900">{formatTs(data.anchored_at)}</span>
          </Field>
          <Field label="Confirmed at">
            <span className="text-slate-900">
              {data.confirmed_at ? formatTs(data.confirmed_at) : "—"}
            </span>
          </Field>
          <Field label="Block number">
            <span className="font-mono text-slate-900 tabular-nums">
              {data.block_number ?? "—"}
            </span>
          </Field>
          <Field label="Transaction">
            <HashDisplay value={data.tx_hash} head={10} tail={6} />
          </Field>
        </dl>
      </section>

      <p className="text-xs leading-relaxed text-slate-500">
        This batch was committed by the LandGuard anchor service. The full
        event range can be recomputed off-chain and the resulting root
        compared byte-for-byte with the value the on-chain contract holds.
      </p>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-caption uppercase tracking-wider text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm">{children}</dd>
    </div>
  );
}
