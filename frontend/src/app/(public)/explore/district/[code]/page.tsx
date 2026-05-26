import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, MapPin } from "lucide-react";
import { StatusPill } from "@/components/common/StatusPill";

// Mirror the pilot/planned dataset from /explore. When rollout
// adds a new district, register it here so the drill-down route
// gates against typos.
const DISTRICTS: Record<
  string,
  {
    name: string;
    region: string;
    parcels: number;
    status: "pilot" | "planned";
    district_id?: number;
    rolloutQuarter?: string;
  }
> = {
  mityana: {
    name: "Mityana",
    region: "Central",
    parcels: 1240,
    status: "pilot",
    district_id: 3,
  },
  wakiso: {
    name: "Wakiso",
    region: "Central",
    parcels: 0,
    status: "planned",
    rolloutQuarter: "Q3 2026",
  },
  "kampala-central": {
    name: "Kampala Central",
    region: "Central",
    parcels: 0,
    status: "planned",
    rolloutQuarter: "Q4 2026",
  },
  gulu: {
    name: "Gulu",
    region: "Northern",
    parcels: 0,
    status: "planned",
    rolloutQuarter: "Q1 2027",
  },
};

export function generateStaticParams() {
  return Object.keys(DISTRICTS).map((code) => ({ code }));
}

export const dynamicParams = false;

export default async function DistrictPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const d = DISTRICTS[code];
  if (!d) notFound();
  const isPilot = d.status === "pilot";

  return (
    <div className="space-y-8">
      <Link
        href="/explore"
        className="inline-flex items-center gap-1 text-sm font-medium text-guard-700 hover:underline"
      >
        <ArrowLeft className="size-4" aria-hidden />
        All districts
      </Link>

      <header className="space-y-2">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          District ledger
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-serif text-3xl font-bold text-slate-900">
            {d.name}
          </h1>
          {isPilot ? (
            <StatusPill kind="verified">Pilot live</StatusPill>
          ) : (
            <StatusPill kind="pending">Planned</StatusPill>
          )}
        </div>
        <p className="max-w-2xl text-sm text-slate-600">
          {d.region} Region
          {isPilot ? (
            <>
              {" · "}
              {d.parcels.toLocaleString()} parcels anchored on chain
            </>
          ) : d.rolloutQuarter ? (
            <>
              {" · "}rollout scheduled for {d.rolloutQuarter}
            </>
          ) : null}
        </p>
      </header>

      {isPilot ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Link
            href="/anchors"
            className="card-surface flex items-start gap-4 transition-colors hover:border-guard-300 hover:bg-guard-50/40"
          >
            <span className="rounded-md bg-guard-50 p-2 text-guard-700">
              <MapPin className="size-5" />
            </span>
            <div className="flex-1 space-y-1.5">
              <h2 className="font-serif text-lg font-semibold text-slate-900">
                Recent anchor batches
              </h2>
              <p className="text-sm text-slate-600">
                Per-batch Merkle roots, transaction hashes, and confirmation
                status from the public anchors index.
              </p>
            </div>
          </Link>
          <Link
            href="/verify"
            className="card-surface flex items-start gap-4 transition-colors hover:border-guard-300 hover:bg-guard-50/40"
          >
            <span className="rounded-md bg-guard-50 p-2 text-guard-700">
              <MapPin className="size-5" />
            </span>
            <div className="flex-1 space-y-1.5">
              <h2 className="font-serif text-lg font-semibold text-slate-900">
                Verify a {d.name} title
              </h2>
              <p className="text-sm text-slate-600">
                Enter a UPI to fetch its Merkle proof and chain confirmation
                from the public verifier.
              </p>
            </div>
          </Link>
        </div>
      ) : (
        <aside className="card-surface state-pending">
          <p className="text-sm leading-relaxed text-slate-700">
            <strong className="text-slate-900">{d.name}</strong> isn&apos;t live
            yet. Anchored data will appear here once the district enrols
            {d.rolloutQuarter ? ` (target: ${d.rolloutQuarter})` : ""}. Until
            then, the only district with live data is{" "}
            <Link
              href="/explore/district/mityana"
              className="text-guard-700 underline underline-offset-4"
            >
              Mityana
            </Link>
            .
          </p>
        </aside>
      )}
    </div>
  );
}
