"use client";

import { useRedactStore } from "@/store/useRedactStore";

/**
 * Applies the `.redact` class to the officer-console subtree when the
 * redact toggle is on. Every element tagged `.redactable` is then blurred
 * (CSS in `globals.css`) until hovered — making it safe to screen-share
 * the console to MoLHUD, journalists, or auditors without leaking PII.
 */
export function RedactShell({ children }: { children: React.ReactNode }) {
  const enabled = useRedactStore((s) => s.enabled);
  return <div className={enabled ? "redact" : undefined}>{children}</div>;
}
