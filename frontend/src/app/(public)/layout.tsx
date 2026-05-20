import Link from "next/link";
import { ChainStatusBeacon } from "@/components/chain/ChainStatusBeacon";
import { MinistryHeader } from "@/components/layout/MinistryHeader";
import { CoatOfArmsMark } from "@/components/layout/CoatOfArmsMark";

/**
 * Public route group — verifier, explorer, anchor browser. Every page sits
 * under the Ministry attribution band so citizens always see the institutional
 * voice. Chrome is muted slate so the page content (especially the verifier
 * QR scanner) carries the visual weight.
 */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <MinistryHeader />

      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-officer items-center justify-between px-6 py-3">
          <Link href="/" className="flex items-center gap-2.5">
            <CoatOfArmsMark size={28} />
            <span>
              <span className="block font-serif text-sm font-semibold leading-none text-slate-900">
                LandGuard
              </span>
              <span className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
                Public registry
              </span>
            </span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <Link href="/verify" className="btn-tertiary px-3">Verify</Link>
            <Link href="/explore" className="btn-tertiary px-3">Explore</Link>
            <Link href="/anchors" className="btn-tertiary px-3">Anchors</Link>
            <span className="mx-2 h-5 w-px bg-slate-200" aria-hidden />
            <ChainStatusBeacon />
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-officer px-6 py-8">{children}</main>

      <footer className="mt-20 border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-officer px-6 py-6 text-xs text-slate-500">
          <p>
            Ministry of Lands, Housing &amp; Urban Development · Republic of Uganda
            · Public verifier, no credentials required.
          </p>
        </div>
      </footer>
    </div>
  );
}
