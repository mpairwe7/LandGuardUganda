"use client";

import { Eye, EyeOff } from "lucide-react";
import { useRedactStore } from "@/store/useRedactStore";

/**
 * Officer console toggle: enables PII redaction for screen-share / projector
 * use. Anything wrapped in `.redactable` gets blurred until hover.
 */
export function RedactToggle() {
  const enabled = useRedactStore((s) => s.enabled);
  const toggle  = useRedactStore((s) => s.toggle);
  return (
    <button
      type="button"
      onClick={toggle}
      title={enabled ? "PII redacted — click to reveal" : "Click to redact PII for screen-share"}
      aria-pressed={enabled}
      className="inline-flex items-center gap-1.5 rounded-md border border-guard-800 px-2.5 py-1 text-xs font-medium text-slate-100 transition-colors hover:bg-guard-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-seal-400"
    >
      {enabled ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
      <span>{enabled ? "Redacted" : "Redact"}</span>
    </button>
  );
}
