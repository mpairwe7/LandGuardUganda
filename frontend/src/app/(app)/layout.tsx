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

/**
 * Officer console — dark institutional chrome (guard-950 header, guard-900
 * sidebar). The main content well stays light slate so documents and
 * certificates read like government paper, not a dashboard. RedactToggle
 * lives in the header so any officer can engage screen-share safe mode in
 * one click.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RedactShell>
      <div className="grid min-h-screen grid-cols-[16rem_1fr] bg-slate-50">
        {/* SIDEBAR --------------------------------------------------------- */}
        <aside className="officer-sidebar flex flex-col border-r border-guard-950 px-4 py-5">
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

          <DistrictPicker />

          <nav className="mt-6 flex-1 space-y-5 text-sm" aria-label="Console navigation">
            <NavGroup label="Citizen">
              <NavLink href="/citizen" icon={ScrollText}>My parcels</NavLink>
            </NavGroup>
            <NavGroup label="Surveyor">
              <NavLink href="/surveyor/register" icon={MapPin}>Register parcel</NavLink>
            </NavGroup>
            <NavGroup label="Land Officer">
              <NavLink href="/officer" icon={UserCheck}>KYC queue</NavLink>
              {/* /officer/alerts and /officer/reviews are surfaced
                  inline on /officer until their standalone routes
                  are built. */}
            </NavGroup>
            <NavGroup label="Registrar">
              <NavLink href="/registrar" icon={FileCheck2}>Issue title</NavLink>
              {/* /registrar/anchor is folded into /registrar for the
                  showcase build. */}
            </NavGroup>
            <NavGroup label="Auditor">
              <NavLink href="/auditor" icon={ShieldCheck}>Chain integrity</NavLink>
            </NavGroup>
          </nav>

          <p className="mt-6 border-t border-guard-800 pt-4 text-[10px] leading-relaxed text-slate-400">
            Every action on this console writes to the tamper-evident audit
            chain. PII access is logged.
          </p>
        </aside>

        {/* MAIN ------------------------------------------------------------ */}
        <div className="flex min-h-screen flex-col">
          <header className="officer-header">
            <div className="flex items-center gap-3">
              <CoatOfArmsMark size={22} variant="light" />
              <span className="font-serif text-[11px] uppercase tracking-[0.18em] text-seal-400">
                Republic of Uganda · MLHUD
              </span>
            </div>
            <div className="flex items-center gap-3">
              <ChainStatusBeacon />
              <RedactToggle />
              <RoleSwitcher />
            </div>
          </header>
          <main className="mx-auto w-full max-w-officer flex-1 px-8 py-8">
            {children}
          </main>
        </div>
      </div>
    </RedactShell>
  );
}

function NavGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
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
}: {
  href: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <li>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <Link href={href as any} className="officer-nav-link">
        <Icon className="size-4 text-slate-400" aria-hidden />
        <span>{children}</span>
      </Link>
    </li>
  );
}
