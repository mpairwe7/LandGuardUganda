"use client";

import { create } from "zustand";

export type DemoAct = "hook" | "problem" | "anchor" | "fraud" | "verify" | "resilience" | "close";

interface DemoState {
  enabled: boolean;
  act: DemoAct;
  rpcKilled: boolean;
  setEnabled: (b: boolean) => void;
  setAct: (a: DemoAct) => void;
  setRpcKilled: (b: boolean) => void;
}

export const useDemoStore = create<DemoState>((set) => ({
  enabled: false,
  act: "hook",
  rpcKilled: false,
  setEnabled: (enabled) => set({ enabled }),
  setAct: (act) => set({ act }),
  setRpcKilled: (rpcKilled) => set({ rpcKilled }),
}));
