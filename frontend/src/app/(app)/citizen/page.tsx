"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ChevronRight, MapPin } from "lucide-react";
import { api } from "@/lib/api";
import { useDistrictStore } from "@/store/useDistrictStore";
import { StatusPill, type StatusKind } from "@/components/common/StatusPill";

interface Parcel {
  parcel_id: string;
  tenure_type: string;
  area_hectares: number;
  status: string;
}

const STATUS_KIND: Record<string, StatusKind> = {
  ACTIVE: "verified",
  DISPUTED: "disputed",
  FROZEN: "frozen",
  REVOKED: "revoked",
  PENDING: "pending",
};

export default function CitizenPage() {
  const districtId = useDistrictStore((s) => s.activeId);
  const { data, isLoading } = useQuery({
    queryKey: ["parcels", "mine", districtId],
    queryFn: () =>
      api.get<Parcel[]>(`/v1/parcels?district_id=${districtId}&limit=20`),
    staleTime: 30_000,
  });

  return (
    <div className="mx-auto max-w-citizen space-y-6">
      <header className="border-b border-slate-200 pb-4">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Citizen portal
        </p>
        <h1 className="font-serif text-2xl font-bold text-slate-900">
          My parcels
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Parcels you have a registered interest in. Tap any row to see its
          title, anchor history, and any disputes.
        </p>
      </header>

      {isLoading && (
        <p className="text-sm text-slate-500">Loading parcels…</p>
      )}

      <ul className="space-y-2.5" role="list">
        {data?.map((p) => (
          <li key={p.parcel_id}>
            <Link
              href={`/titles/${encodeURIComponent(p.parcel_id)}` as never}
              className="card-surface grid grid-cols-[auto_1fr_auto_auto] items-center gap-4 transition-colors hover:border-guard-300 hover:bg-guard-50/30"
            >
              <span className="rounded-md bg-guard-50 p-2 text-guard-700">
                <MapPin className="size-4" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="font-mono text-sm font-medium text-slate-900 redactable">
                  {p.parcel_id}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {p.tenure_type} · {p.area_hectares.toFixed(2)} ha
                </p>
              </div>
              <StatusPill kind={STATUS_KIND[p.status] ?? "neutral"}>
                {p.status}
              </StatusPill>
              <ChevronRight
                className="size-4 text-slate-400"
                aria-label="View"
              />
            </Link>
          </li>
        ))}
        {(!data || data.length === 0) && !isLoading && (
          <li className="card-surface text-center text-sm text-slate-500">
            No parcels in this district yet.
          </li>
        )}
      </ul>
    </div>
  );
}
