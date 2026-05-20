"use client";

import { create } from "zustand";

interface RedactState {
  enabled: boolean;
  toggle: () => void;
  setEnabled: (v: boolean) => void;
}

/**
 * Officer-console privacy toggle: blurs every element with the `.redactable`
 * class so an officer can present their screen (to MoLHUD, a journalist, a
 * district auditor) without leaking PII. Hover briefly reveals the value.
 *
 * Globally-applied via the `.redact` class on the app shell when enabled.
 */
export const useRedactStore = create<RedactState>((set, get) => ({
  enabled: false,
  toggle: () => set({ enabled: !get().enabled }),
  setEnabled: (enabled) => set({ enabled }),
}));
