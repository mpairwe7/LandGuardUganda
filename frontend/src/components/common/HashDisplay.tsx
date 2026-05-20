"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { cn } from "@/lib/cn";

interface Props {
  value: string | null | undefined;
  head?: number;
  tail?: number;
  label?: string;
  className?: string;
  copy?: boolean;
}

/**
 * Truncated monospace hash with copy-to-clipboard.
 *
 *   0xab12 … cd34   [copy]
 *
 * The full value is preserved in the title attribute, in copy, and behind the
 * mono-spaced ellipsis — so screen readers can dictate it on demand.
 */
export function HashDisplay({
  value,
  head = 6,
  tail = 4,
  label,
  className,
  copy = true,
}: Props) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-slate-400">—</span>;
  const stripped = value.startsWith("0x") ? value.slice(2) : value;
  const display =
    stripped.length <= head + tail
      ? value
      : `${value.startsWith("0x") ? "0x" : ""}${stripped.slice(0, head)}…${stripped.slice(-tail)}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard denied — soft failure */
    }
  };

  return (
    <span className={cn("inline-flex items-center gap-1.5 font-mono text-xs", className)}>
      {label && <span className="text-slate-500">{label}</span>}
      <span title={value} className="redactable text-slate-800">
        {display}
      </span>
      {copy && (
        <button
          type="button"
          onClick={handleCopy}
          className="rounded p-0.5 text-slate-400 transition-colors hover:text-guard-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-guard-600"
          aria-label="Copy full value"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        </button>
      )}
    </span>
  );
}
