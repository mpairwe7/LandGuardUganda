"use client";

import type { ReactNode } from "react";
import {
  ShieldCheck,
  Clock,
  AlertTriangle,
  Lock,
  Link as LinkIcon,
  CheckCircle2,
  Gavel,
  Ban,
} from "lucide-react";
import { cn } from "@/lib/cn";

export type StatusKind =
  | "verified"
  | "pending"
  | "flag"
  | "frozen"
  | "chain"
  | "neutral"
  | "disputed"
  | "revoked";

const META: Record<StatusKind, { cls: string; Icon: typeof ShieldCheck; aria: string }> = {
  verified: { cls: "pill-verified",         Icon: ShieldCheck,    aria: "verified, anchored on chain" },
  pending:  { cls: "pill-pending",          Icon: Clock,          aria: "pending anchor" },
  flag:     { cls: "pill-flag",             Icon: AlertTriangle,  aria: "under human review" },
  frozen:   { cls: "pill-frozen",           Icon: Lock,           aria: "frozen" },
  chain:    { cls: "pill-chain",            Icon: LinkIcon,       aria: "on chain" },
  neutral:  { cls: "pill-neutral",          Icon: CheckCircle2,   aria: "neutral status" },
  disputed: { cls: "pill-flag",             Icon: Gavel,          aria: "disputed" },
  revoked:  { cls: "pill-frozen",           Icon: Ban,            aria: "revoked" },
};

interface Props {
  kind: StatusKind;
  children: ReactNode;
  className?: string;
}

/**
 * Canonical status indicator: colour + icon + text label. The colour alone
 * never carries meaning (WCAG 2.2 §1.4.1). The aria-label spells the status
 * out for screen readers regardless of icon support.
 */
export function StatusPill({ kind, children, className }: Props) {
  const { cls, Icon, aria } = META[kind];
  return (
    <span className={cn(cls, className)} aria-label={aria} role="status">
      <Icon className="size-3.5" aria-hidden />
      <span>{children}</span>
    </span>
  );
}
