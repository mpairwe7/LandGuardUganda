"use client";

import { useDistrictStore, DEMO_DISTRICTS } from "@/store/useDistrictStore";

/**
 * District selector — sits in the officer console sidebar. Styled for the
 * dark guard-900 surface; falls back to a slate light surface when used
 * outside the console (just specify a `light` prop if needed in future).
 */
export function DistrictPicker() {
  const activeId = useDistrictStore((s) => s.activeId);
  const setActive = useDistrictStore((s) => s.setActive);
  return (
    <div>
      <label
        htmlFor="district-picker"
        className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400"
      >
        Active district
      </label>
      <select
        id="district-picker"
        value={activeId}
        onChange={(e) => setActive(Number(e.target.value))}
        className="mt-1.5 w-full rounded-md border border-guard-800 bg-guard-950 px-2.5 py-1.5 text-sm text-slate-100 focus:border-seal-400 focus:outline-none focus:ring-1 focus:ring-seal-400"
      >
        {DEMO_DISTRICTS.map((d) => (
          <option key={d.id} value={d.id} className="bg-white text-slate-900">
            {d.name} · {d.region}
          </option>
        ))}
      </select>
    </div>
  );
}
