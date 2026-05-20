"use client";

import { create } from "zustand";

export type ChainBreakerState = "closed" | "half_open" | "open" | "unknown";

interface ChainStatusState {
  breaker: ChainBreakerState;
  lastAnchorAt: number | null;
  pendingBatches: number;
  setBreaker: (s: ChainBreakerState) => void;
  setLastAnchorAt: (ts: number | null) => void;
  setPending: (n: number) => void;
}

export const useChainStatusStore = create<ChainStatusState>((set) => ({
  breaker: "unknown",
  lastAnchorAt: null,
  pendingBatches: 0,
  setBreaker: (breaker) => set({ breaker }),
  setLastAnchorAt: (lastAnchorAt) => set({ lastAnchorAt }),
  setPending: (pendingBatches) => set({ pendingBatches }),
}));
