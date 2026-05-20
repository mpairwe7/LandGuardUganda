"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type Role =
  | "CITIZEN"
  | "SURVEYOR"
  | "LAND_OFFICER"
  | "REGISTRAR"
  | "AUDITOR"
  | "PUBLIC_VERIFIER"
  | "ADMIN";

interface AuthState {
  token: string | null;
  userId: string | null;
  role: Role | null;
  fullName: string | null;
  demoRole: Role | null;
  demoDistrictId: number | null;
  setSession: (params: {
    token: string;
    userId: string;
    role: Role;
    fullName: string;
  }) => void;
  setDemoRole: (role: Role | null, districtId: number | null) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      role: null,
      fullName: null,
      demoRole: null,
      demoDistrictId: null,
      setSession: ({ token, userId, role, fullName }) =>
        set({ token, userId, role, fullName }),
      setDemoRole: (demoRole, demoDistrictId) =>
        set({ demoRole, demoDistrictId }),
      clear: () =>
        set({
          token: null,
          userId: null,
          role: null,
          fullName: null,
          demoRole: null,
          demoDistrictId: null,
        }),
    }),
    {
      name: "landguard.auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        demoRole: s.demoRole,
        demoDistrictId: s.demoDistrictId,
        // Note: real tokens deliberately NOT persisted; they live for the session only.
      }),
    },
  ),
);
