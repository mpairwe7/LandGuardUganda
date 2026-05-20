import { AnchorTimeline } from "@/components/chain/AnchorTimeline";

export const metadata = {
  title: "Anchor explorer",
  description:
    "Public ledger of every Merkle root LandGuard Uganda has committed to a blockchain.",
};

/**
 * Public anchor explorer. Every district periodically commits a Merkle
 * root of its land-record events to the blockchain; each row is one batch.
 * Read-only, no credentials.
 */
export default function AnchorsPage() {
  return (
    <div className="mx-auto max-w-citizen space-y-6">
      <header className="space-y-2">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Public ledger
        </p>
        <h1 className="font-serif text-3xl font-bold text-slate-900">
          Anchor explorer
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-slate-600">
          Every district periodically commits a Merkle root of its
          land-record events to a public blockchain. Each row below is one
          batch — click for the full event range and the on-chain
          transaction.
        </p>
      </header>
      <AnchorTimeline />
    </div>
  );
}
