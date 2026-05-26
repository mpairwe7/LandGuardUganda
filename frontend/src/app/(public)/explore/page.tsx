import Link from "next/link";
import { MapPin, ArrowRight } from "lucide-react";
import { StatusPill } from "@/components/common/StatusPill";

export const metadata = {
  title: "Explore the registry",
  description:
    "Read-only district view of LandGuard Uganda's pilot land registry.",
};

const PILOT_DISTRICTS = [
  { code: "mityana", name: "Mityana", region: "Central", parcels: 1240, status: "pilot" as const },
  { code: "wakiso", name: "Wakiso", region: "Central", parcels: 0, status: "planned" as const },
  { code: "kampala-central", name: "Kampala Central", region: "Central", parcels: 0, status: "planned" as const },
  { code: "gulu", name: "Gulu", region: "Northern", parcels: 0, status: "planned" as const },
];

/**
 * Public-facing district browser. The Mityana pilot is the one with live data;
 * other districts surface their planned rollout state so the registry's roadmap
 * is visible to citizens and evaluators.
 */
export default function ExplorePage() {
  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Public registry
        </p>
        <h1 className="font-serif text-3xl font-bold text-slate-900">
          Explore by district
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-slate-600">
          LandGuard Uganda anchors each district&apos;s ledger independently.
          The Mityana pilot is live; remaining districts are scheduled for
          rollout in 2026–27 alongside the Ministry of Lands, Housing &amp;
          Urban Development.
        </p>
      </header>

      <ul className="grid gap-4 sm:grid-cols-2">
        {PILOT_DISTRICTS.map((d) => {
          const isPilot = d.status === "pilot";
          return (
            <li key={d.code}>
              <Link
                href={`/explore/district/${d.code}`}
                className={`card-surface flex items-start gap-4 transition-colors hover:border-guard-300 hover:bg-guard-50/40 ${
                  isPilot ? "state-verified" : ""
                }`}
              >
                <span className="rounded-md bg-guard-50 p-2 text-guard-700">
                  <MapPin className="size-5" />
                </span>
                <div className="flex-1 space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="font-serif text-lg font-semibold text-slate-900">
                      {d.name}
                    </h2>
                    {isPilot ? (
                      <StatusPill kind="verified">Pilot live</StatusPill>
                    ) : (
                      <StatusPill kind="pending">Planned</StatusPill>
                    )}
                  </div>
                  <p className="text-sm text-slate-600">
                    {d.region} Region · {d.parcels.toLocaleString()} parcels on
                    chain
                  </p>
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-guard-700">
                    View district
                    <ArrowRight className="size-3.5" aria-hidden />
                  </span>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>

      <aside className="card-surface state-pending">
        <p className="text-sm leading-relaxed text-slate-700">
          <strong className="text-slate-900">No login required.</strong> Click a
          district to see its anchored parcels, recent batches, and the chain
          transactions that confirm them. To verify a specific title, visit{" "}
          <Link href="/verify" className="text-guard-700 underline underline-offset-4">
            the public verifier
          </Link>
          .
        </p>
      </aside>
    </div>
  );
}
