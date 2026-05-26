import Link from "next/link";
import { ChainStatusBeacon } from "@/components/chain/ChainStatusBeacon";
import { LocaleSwitcher } from "@/components/layout/LocaleSwitcher";
import { MinistryHeader } from "@/components/layout/MinistryHeader";
import { CoatOfArmsMark } from "@/components/layout/CoatOfArmsMark";
import { MobileMenu } from "@/components/layout/MobileMenu";

/**
 * Public route group — verifier, explorer, anchor browser. Every page sits
 * under the Ministry attribution band so citizens always see the institutional
 * voice. Chrome is muted slate so the page content (especially the verifier
 * QR scanner) carries the visual weight.
 *
 * Responsive strategy: a single inline nav at sm:+ (≥640 px); below
 * that, the nav links collapse into a hamburger drawer. The chain-status
 * beacon stays visible on the header at every width because the
 * "is the system live?" answer is the most important piece of public
 * information.
 */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <MinistryHeader />

      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-officer items-center justify-between gap-2 px-4 py-3 sm:gap-4 sm:px-6">
          <Link href="/" className="flex min-w-0 items-center gap-2.5">
            <CoatOfArmsMark size={28} />
            <span className="min-w-0">
              <span className="block truncate font-serif text-sm font-semibold leading-none text-slate-900">
                LandGuard
              </span>
              <span className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
                Public registry
              </span>
            </span>
          </Link>

          {/* Full inline nav — sm:+ only. */}
          <nav className="hidden items-center gap-1 text-sm sm:flex">
            <Link href="/verify" className="btn-tertiary px-3">Verify</Link>
            <Link href="/explore" className="btn-tertiary px-3">Explore</Link>
            <Link href="/anchors" className="btn-tertiary px-3">Anchors</Link>
            <span className="mx-2 h-5 w-px bg-slate-200" aria-hidden />
            <ChainStatusBeacon />
            <span className="mx-2 h-5 w-px bg-slate-200" aria-hidden />
            <LocaleSwitcher />
          </nav>

          {/* Compact nav — phone widths. */}
          <div className="flex items-center gap-2 sm:hidden">
            <ChainStatusBeacon />
            <MobileMenu
              triggerLabel="Open public registry menu"
              side="right"
              triggerClassName="inline-flex size-9 items-center justify-center rounded-md text-slate-700 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-guard-600 focus-visible:ring-offset-2"
              headerSlot={
                <div className="flex items-center gap-2.5">
                  <CoatOfArmsMark size={24} />
                  <span>
                    <span className="block font-serif text-sm font-semibold leading-none text-slate-900">
                      LandGuard
                    </span>
                    <span className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
                      Public registry
                    </span>
                  </span>
                </div>
              }
            >
              <nav className="flex flex-col gap-1 text-sm" aria-label="Public registry navigation">
                <Link
                  href="/verify"
                  className="rounded-md px-3 py-2 text-slate-800 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-guard-600"
                >
                  Verify a title
                </Link>
                <Link
                  href="/explore"
                  className="rounded-md px-3 py-2 text-slate-800 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-guard-600"
                >
                  Explore districts
                </Link>
                <Link
                  href="/anchors"
                  className="rounded-md px-3 py-2 text-slate-800 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-guard-600"
                >
                  Anchor explorer
                </Link>
                <div className="my-2 h-px bg-slate-200" aria-hidden />
                <div className="px-3 py-2">
                  <LocaleSwitcher />
                </div>
              </nav>
            </MobileMenu>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-officer px-4 py-6 sm:px-6 sm:py-8">{children}</main>

      <footer className="mt-16 border-t border-slate-200 bg-white sm:mt-20">
        <div className="mx-auto max-w-officer px-4 py-6 text-xs text-slate-500 sm:px-6">
          <p>
            Ministry of Lands, Housing &amp; Urban Development · Republic of Uganda
            · Public verifier, no credentials required.
          </p>
        </div>
      </footer>
    </div>
  );
}
