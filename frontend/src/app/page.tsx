import Link from "next/link";
import { Suspense } from "react";
import {
  ShieldCheck,
  Globe,
  Layers,
  ScanLine,
  Activity,
  ArrowRight,
} from "lucide-react";
import { LatestAnchorBadge } from "@/components/chain/LatestAnchorBadge";
import { MinistryHeader } from "@/components/layout/MinistryHeader";
import { CoatOfArmsMark } from "@/components/layout/CoatOfArmsMark";
import { StatusPill } from "@/components/common/StatusPill";

export const dynamic = "force-dynamic";

/**
 * Public landing — the institutional front door.
 *
 * Voice: government attribution → problem → mechanism → call-to-action.
 * Gold ink is reserved for seal marks and on-chain confirmation. All
 * primary actions route to the public verifier (the showcase moment).
 */
export default function PublicLanding() {
  return (
    <div className="min-h-screen bg-slate-50">
      <MinistryHeader />

      {/* Application chrome under the ministry band */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-officer items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2.5">
            <CoatOfArmsMark size={32} />
            <span>
              <span className="block font-serif text-base font-semibold leading-none text-slate-900">
                LandGuard
              </span>
              <span className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Uganda
              </span>
            </span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <Link href="/verify" className="btn-tertiary px-3">
              Verify a title
            </Link>
            <Link href="/explore" className="btn-tertiary px-3">
              Explore
            </Link>
            <Link href="/anchors" className="btn-tertiary px-3">
              Anchor explorer
            </Link>
            <Link href="/citizen" className="btn-primary ml-2">
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-officer px-6 py-12 lg:py-20">
        {/* HERO ----------------------------------------------------------- */}
        <section className="grid items-start gap-12 lg:grid-cols-[1.15fr_1fr]">
          <div className="space-y-7">
            <Suspense
              fallback={
                <StatusPill kind="pending">Loading chain state…</StatusPill>
              }
            >
              <LatestAnchorBadge />
            </Suspense>

            <h1 className="text-balance font-serif text-4xl font-bold leading-[1.08] tracking-tight text-slate-900 md:text-5xl lg:text-[3.25rem]">
              Land records that{" "}
              <span className="text-guard-700">no one can fake</span>.
            </h1>

            <p className="max-w-prose text-pretty text-lg leading-relaxed text-slate-700">
              Sixty percent of Uganda&apos;s land has unclear or contested
              ownership. LandGuard pairs a district-level hash-chained ledger
              with a public blockchain anchor, so every title can be verified
              by anyone — citizen, registrar, journalist, foreign investor —
              with a single QR scan.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                href="/verify"
                className="btn-primary"
              >
                <ScanLine className="size-4" />
                <span>Verify a title now</span>
              </Link>
              <Link href="/anchors" className="btn-secondary">
                <Activity className="size-4" />
                <span>See live anchors</span>
              </Link>
              <Link
                href="/explore"
                className="btn-tertiary"
              >
                Explore the registry
                <ArrowRight className="size-3.5" />
              </Link>
            </div>

            <p className="border-l-2 border-seal-400 bg-seal-50/40 pl-4 py-2 text-xs leading-relaxed text-slate-600">
              <span className="font-serif font-semibold uppercase tracking-[0.16em] text-guard-800">
                Submission
              </span>{" "}
              · National Innovator Registry 2026 · Ministry of ICT &amp;
              National Guidance · Showcase 25 June 2026 at Serena Conference
              Centre, Kampala.
            </p>
          </div>

          {/* MECHANISM CARD */}
          <aside className="card-elevated">
            <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
              How it works
            </p>
            <h2 className="mt-1 font-serif text-xl font-semibold text-slate-900">
              Off-chain speed, on-chain trust.
            </h2>
            <ol className="mt-5 space-y-5 text-sm">
              <Step
                n={1}
                title="Off-chain ledger (instant)"
                icon={Layers}
                body="Every title issuance, transfer, KYC, and dispute becomes a hash-chained event in the district's append-only ledger."
              />
              <Step
                n={2}
                title="On-chain anchor (every few minutes)"
                icon={Globe}
                body={
                  <>
                    A Merkle root of the batch is committed to an Ethereum-
                    compatible chain via{" "}
                    <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[11px] text-slate-800">
                      LandRegistryAnchor.sol
                    </code>
                    .
                  </>
                }
              />
              <Step
                n={3}
                title="Public verifier (anyone, anytime)"
                icon={ShieldCheck}
                body="Scan the QR on a title. The proof is verified against the on-chain root — no trust in LandGuard required."
              />
            </ol>
          </aside>
        </section>

        {/* STAT BAND ------------------------------------------------------- */}
        <section className="mt-20 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Tenant boundaries" value="Per-district chains" />
          <Stat label="Cost per anchor" value="≈ pennies / batch" />
          <Stat label="Off-chain speed" value="< 100 ms writes" />
          <Stat label="Resilience" value="Works during chain outage" />
        </section>

        {/* FOR EVALUATORS -------------------------------------------------- */}
        <section className="mt-16 card-surface state-verified">
          <div className="flex items-start gap-4">
            <ShieldCheck className="mt-0.5 size-6 shrink-0 text-status-verified" aria-hidden />
            <div className="flex-1 space-y-2">
              <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
                For evaluators
              </p>
              <h2 className="font-serif text-xl font-semibold text-slate-900">
                Every claim is reproducible from this repository.
              </h2>
              <p className="max-w-prose text-sm leading-relaxed text-slate-700">
                A prototype submission to the Uganda MoICT&amp;NG National
                Innovator Registry. The smart contract, audit ledger, and
                public verifier are independently auditable. See the{" "}
                <Link href="/anchors" className="text-guard-700 underline underline-offset-4">
                  anchor explorer
                </Link>{" "}
                for live batches and the{" "}
                <Link href="/demo" className="text-guard-700 underline underline-offset-4">
                  demo control panel
                </Link>{" "}
                for the showcase storyboard.
              </p>
            </div>
          </div>
        </section>

        {/* FOOTER ---------------------------------------------------------- */}
        <footer className="mt-20 border-t border-slate-200 pt-8 text-sm text-slate-600">
          <div className="grid gap-6 sm:grid-cols-3">
            <div>
              <p className="font-serif text-[11px] font-semibold uppercase tracking-[0.18em] text-guard-700">
                Open architecture
              </p>
              <p className="mt-2 leading-relaxed">
                Ready for Sepolia today; portable to EAC regional chains or a
                Ugandan permissioned chain tomorrow.
              </p>
            </div>
            <div>
              <p className="font-serif text-[11px] font-semibold uppercase tracking-[0.18em] text-guard-700">
                Contact
              </p>
              <p className="mt-2 leading-relaxed">
                <a
                  href="mailto:kalemaaaaaaaa@gmail.com"
                  className="text-slate-700 underline underline-offset-4"
                >
                  kalemaaaaaaaa@gmail.com
                </a>
              </p>
            </div>
            <div>
              <p className="font-serif text-[11px] font-semibold uppercase tracking-[0.18em] text-guard-700">
                Citizen access
              </p>
              <p className="mt-2 leading-relaxed">
                Verify any title via USSD{" "}
                <span className="font-mono text-slate-800">*247*256#</span> — no
                smartphone required.
              </p>
            </div>
          </div>
          <p className="mt-8 text-xs text-slate-500">
            © 2026 LandGuard Uganda · Built for the Republic of Uganda · This
            prototype does not yet hold the seal of the Office of the
            President.
          </p>
        </footer>
      </main>
    </div>
  );
}

function Step({
  n,
  title,
  body,
  icon: Icon,
}: {
  n: number;
  title: string;
  body: React.ReactNode;
  icon: React.ElementType;
}) {
  return (
    <li className="flex items-start gap-3">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-guard-200 bg-guard-50 font-serif text-xs font-semibold text-guard-700">
        {n}
      </span>
      <div>
        <p className="flex items-center gap-1.5 font-medium text-slate-900">
          <Icon className="size-4 text-guard-700" aria-hidden />
          {title}
        </p>
        <p className="mt-1 text-slate-600">{body}</p>
      </div>
    </li>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card-surface">
      <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 font-serif text-xl font-semibold text-slate-900">
        {value}
      </p>
    </div>
  );
}
