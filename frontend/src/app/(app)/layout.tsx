import Link from "next/link";
import {
  MapPin,
  ScrollText,
  UserCheck,
  FileCheck2,
  ShieldCheck,
} from "lucide-react";
import { ChainStatusBeacon } from "@/components/chain/ChainStatusBeacon";
import { DistrictPicker } from "@/components/layout/DistrictPicker";
import { RoleSwitcher } from "@/components/layout/RoleSwitcher";
import { RedactToggle } from "@/components/layout/RedactToggle";
import { CoatOfArmsMark } from "@/components/layout/CoatOfArmsMark";
import { RedactShell } from "@/components/layout/RedactShell";
import { MobileMenu } from "@/components/layout/MobileMenu";

/**
 * Officer console — dark institutional chrome (guard-950 header, guard-900
 * sidebar). The main content well stays light slate so documents and
 * certificates read like government paper, not a dashboard. RedactToggle
 * lives in the header so any officer can engage screen-share safe mode in
 * one click.
 *
 * Responsive strategy: the sidebar is a permanent fixture at lg:+
 * (≥1024 px); below that it collapses behind a hamburger MobileMenu in
 * the top header. DistrictPicker + nav links render the same in both
 * forms — the source of truth is `<Sidebar />` below.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RedactShell>
      <div className="grid min-h-screen bg-slate-50 lg:grid-cols-[16rem_1fr]">
        {/* DESKTOP SIDEBAR --------------------------------------------------- */}
        <aside className="officer-sidebar hidden flex-col border-r border-guard-950 px-4 py-5 lg:flex">
          <Sidebar />
        </aside>

        {/* MAIN ------------------------------------------------------------- */}
        <div className="flex min-h-screen flex-col">
          <header className="officer-header gap-2">
            {/* Mobile-only hamburger; hidden at lg:+ where the sidebar
                is already visible. */}
            <div className="lg:hidden">
              <MobileMenu
                triggerLabel="Open console navigation"
                triggerClassName="inline-flex size-9 items-center justify-center rounded-md text-white hover:bg-guard-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-seal-300 focus-visible:ring-offset-2"
                headerSlot={
                  <div className="flex items-center gap-2.5">
                    <CoatOfArmsMark size={28} />
                    <span>
                      <span className="block font-serif text-sm font-semibold leading-none text-slate-900">
                        LandGuard
                      </span>
                      <span className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
                        Officer console
                      </span>
                    </span>
                  </div>
                }
              >
                {/* Same Sidebar component, dropped into the drawer in
                    light-theme form. */}
                <div className="officer-sidebar-mobile flex flex-col gap-4">
                  <Sidebar variant="mobile" />
                </div>
              </MobileMenu>
            </div>

            <div className="flex flex-1 items-center gap-2 sm:gap-3">
              <CoatOfArmsMark size={22} variant="light" />
              <span className="hidden font-serif text-[11px] uppercase tracking-[0.18em] text-seal-400 sm:inline">
                Republic of Uganda · MLHUD
              </span>
              <span className="font-serif text-[11px] uppercase tracking-[0.18em] text-seal-400 sm:hidden">
                MLHUD
              </span>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              <ChainStatusBeacon />
              <RedactToggle />
              <RoleSwitcher />
            </div>
          </header>
          <main className="mx-auto w-full max-w-officer flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            {children}
          </main>
        </div>
      </div>
    </RedactShell>
  );
}

/**
 * The single source of truth for sidebar contents. Renders the same
 * brand, district picker, and nav list in two themes:
 *   - default (dark, on guard-900 sidebar)
 *   - mobile  (light, inside the MobileMenu drawer on white)
 */
function Sidebar({ variant = "default" }: { variant?: "default" | "mobile" }) {
  const isMobile = variant === "mobile";
  return (
    <>
      {!isMobile && (
        <Link href="/" className="mb-6 flex items-center gap-2.5">
          <CoatOfArmsMark size={32} variant="light" />
          <span>
            <span className="block font-serif text-base font-semibold leading-none text-white">
              LandGuard
            </span>
            <span className="text-[10px] uppercase tracking-[0.18em] text-seal-400">
              Officer console
            </span>
          </span>
        </Link>
      )}

      <DistrictPicker />

      <nav
        className={`flex-1 space-y-5 text-sm ${isMobile ? "mt-4" : "mt-6"}`}
        aria-label="Console navigation"
      >
        <NavGroup label="Citizen" variant={variant}>
          <NavLink href="/citizen" icon={ScrollText} variant={variant}>
            My parcels
          </NavLink>
        </NavGroup>
        <NavGroup label="Surveyor" variant={variant}>
          <NavLink href="/surveyor/register" icon={MapPin} variant={variant}>
            Register parcel
          </NavLink>
        </NavGroup>
        <NavGroup label="Land Officer" variant={variant}>
          <NavLink href="/officer" icon={UserCheck} variant={variant}>
            KYC queue
          </NavLink>
        </NavGroup>
        <NavGroup label="Registrar" variant={variant}>
          <NavLink href="/registrar" icon={FileCheck2} variant={variant}>
            Issue title
          </NavLink>
        </NavGroup>
        <NavGroup label="Auditor" variant={variant}>
          <NavLink href="/auditor" icon={ShieldCheck} variant={variant}>
            Chain integrity
          </NavLink>
        </NavGroup>
      </nav>

      <p
        className={`mt-6 border-t pt-4 text-[10px] leading-relaxed ${
          isMobile
            ? "border-slate-200 text-slate-600"
            : "border-guard-800 text-slate-400"
        }`}
      >
        Every action on this console writes to the tamper-evident audit
        chain. PII access is logged.
      </p>
    </>
  );
}

function NavGroup({
  label,
  children,
  variant = "default",
}: {
  label: string;
  children: React.ReactNode;
  variant?: "default" | "mobile";
}) {
  return (
    <div>
      <p
        className={`px-2 text-[10px] font-semibold uppercase tracking-[0.18em] ${
          // Dark sidebar (default): slate-300 (~8.8:1 on guard-900).
          // Mobile drawer is light: slate-600 carries the muted-header role.
          variant === "mobile" ? "text-slate-600" : "text-slate-300"
        }`}
      >
        {label}
      </p>
      <ul className="mt-1 space-y-0.5">{children}</ul>
    </div>
  );
}

function NavLink({
  href,
  icon: Icon,
  children,
  variant = "default",
}: {
  href: string;
  icon: React.ElementType;
  children: React.ReactNode;
  variant?: "default" | "mobile";
}) {
  return (
    <li>
      <Link
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        href={href as any}
        className={
          variant === "mobile"
            ? "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-slate-800 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-guard-600"
            : "officer-nav-link"
        }
      >
        <Icon
          className={`size-4 ${variant === "mobile" ? "text-slate-500" : "text-slate-400"}`}
          aria-hidden
        />
        <span>{children}</span>
      </Link>
    </li>
  );
}
