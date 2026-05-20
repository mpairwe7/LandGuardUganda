"use client";

import { StatusPill } from "@/components/common/StatusPill";

/**
 * Title-level chain state pill. A pending anchor is **not** a failure state —
 * the title is legally valid off-chain until the next batch flush. We use the
 * pending (amber) tone, never red.
 */
export function PendingAnchorBadge({ anchored }: { anchored: boolean }) {
  if (anchored) {
    return <StatusPill kind="verified">Anchored on-chain</StatusPill>;
  }
  return (
    <StatusPill kind="pending" className="animate-pulse-slow">
      Anchor pending — valid off-chain
    </StatusPill>
  );
}
