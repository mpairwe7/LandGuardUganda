import { CoatOfArmsMark } from "./CoatOfArmsMark";

/**
 * Government attribution band — sits above the application chrome on every
 * public-facing surface. Establishes the institutional voice in 24mm of
 * vertical space: coat of arms + ministry name + tagline.
 *
 * Mirrors the visual pattern used across MoICT&NG digital estates
 * (ict.go.ug, nita.go.ug, mlhud.go.ug).
 */
export function MinistryHeader() {
  return (
    <div className="border-b border-guard-900/40 bg-guard-950 text-slate-100">
      <div className="mx-auto flex max-w-officer items-center gap-3 px-6 py-2.5">
        <CoatOfArmsMark size={28} />
        <div className="flex flex-col leading-tight">
          <span className="font-serif text-[11px] uppercase tracking-[0.18em] text-seal-400">
            Republic of Uganda
          </span>
          <span className="text-[12px] font-medium tracking-tight text-slate-200">
            Ministry of Lands, Housing &amp; Urban Development
          </span>
        </div>
        <span className="ml-auto hidden text-[11px] uppercase tracking-wider text-slate-400 sm:inline">
          National Innovator Registry submission · 2026
        </span>
      </div>
    </div>
  );
}
