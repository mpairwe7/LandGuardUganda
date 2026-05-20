"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export interface District {
  id: number;
  name: string;
  region: string;
}

export const DEMO_DISTRICTS: District[] = [
  { id: 1, name: "Kampala Central", region: "Central" },
  { id: 2, name: "Wakiso", region: "Central" },
  { id: 3, name: "Mityana", region: "Central" },
  { id: 4, name: "Gulu", region: "Northern" },
];

interface DistrictState {
  activeId: number;
  setActive: (id: number) => void;
}

export const useDistrictStore = create<DistrictState>()(
  persist(
    (set) => ({
      activeId: 3, // Default to Mityana — the showcase hero district.
      setActive: (activeId) => set({ activeId }),
    }),
    {
      name: "landguard.district",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
