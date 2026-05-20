"use client";

import { useAuthStore, type Role } from "@/store/useAuthStore";
import { useDistrictStore } from "@/store/useDistrictStore";

const ROLES: Role[] = [
  "CITIZEN",
  "SURVEYOR",
  "LAND_OFFICER",
  "REGISTRAR",
  "AUDITOR",
  "ADMIN",
];

/**
 * Demo-mode role picker. Lives in the officer-console header so the
 * presenter can switch personas mid-demo (citizen → surveyor → registrar →
 * officer → auditor) without re-authenticating. Hidden in production builds
 * via auth gating.
 */
export function RoleSwitcher() {
  const demoRole = useAuthStore((s) => s.demoRole);
  const setDemoRole = useAuthStore((s) => s.setDemoRole);
  const districtId = useDistrictStore((s) => s.activeId);
  return (
    <div className="flex items-center gap-2">
      <label
        htmlFor="role-switcher"
        className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400"
      >
        Demo role
      </label>
      <select
        id="role-switcher"
        value={demoRole ?? ""}
        onChange={(e) =>
          setDemoRole((e.target.value || null) as Role | null, districtId)
        }
        className="rounded-md border border-guard-800 bg-guard-950 px-2 py-1 text-xs text-slate-100 focus:border-seal-400 focus:outline-none focus:ring-1 focus:ring-seal-400"
      >
        <option value="" className="bg-white text-slate-900">
          (none)
        </option>
        {ROLES.map((r) => (
          <option key={r} value={r} className="bg-white text-slate-900">
            {r}
          </option>
        ))}
      </select>
    </div>
  );
}
