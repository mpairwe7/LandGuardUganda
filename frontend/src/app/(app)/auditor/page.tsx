"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { useDistrictStore } from "@/store/useDistrictStore";
import { AnchorTimeline } from "@/components/chain/AnchorTimeline";
import { Button } from "@/components/common/Button";
import { StatusPill } from "@/components/common/StatusPill";

interface VerifyReport {
  tenant_id: string;
  total_events: number;
  verified: boolean;
  first_corrupt_seq: number | null;
  reason: string | null;
}

/**
 * Auditor console — Act 6 of the showcase. Walks the per-district hash
 * chain row-by-row and verifies integrity. Independent of the LandGuard
 * service code: the auditor only needs to trust the verifier code, which
 * is open-source.
 */
export default function AuditorPage() {
  const districtId = useDistrictStore((s) => s.activeId);
  const [report, setReport] = useState<VerifyReport | null>(null);

  const run = useMutation({
    mutationFn: () =>
      api.get<VerifyReport>(`/v1/admin/audit/verify/${districtId}`),
    onSuccess: setReport,
  });

  return (
    <div className="space-y-6">
      <header className="border-b border-slate-200 pb-4">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Auditor console
        </p>
        <h1 className="font-serif text-2xl font-bold text-slate-900">
          Chain integrity
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Walk the per-district hash chain and verify every row. Independent
          — the auditor does not need to trust the LandGuard service code,
          only the open-source verifier.
        </p>
      </header>

      <section className="card-surface flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Activity className="size-5 text-guard-700" aria-hidden />
          <div>
            <p className="text-sm font-medium text-slate-900">
              Run chain verification for district{" "}
              <span className="font-mono">{districtId}</span>
            </p>
            <p className="text-xs text-slate-500">
              Each event row is recomputed from{" "}
              <code className="font-mono">prev_hash + payload_hash</code> and
              compared to the stored hash.
            </p>
          </div>
        </div>
        <Button
          variant="primary"
          icon={<ShieldCheck className="size-4" />}
          onClick={() => run.mutate()}
          loading={run.isPending}
        >
          Verify now
        </Button>
      </section>

      {report && (
        <section
          className={`card-surface flex items-start gap-4 ${
            report.verified ? "state-verified" : "state-frozen"
          }`}
        >
          {report.verified ? (
            <>
              <ShieldCheck
                className="size-6 shrink-0 text-status-verified"
                aria-hidden
              />
              <div className="flex-1 space-y-2">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <p className="font-serif text-lg font-semibold text-slate-900">
                    Chain verified
                  </p>
                  <StatusPill kind="verified">
                    {report.total_events.toLocaleString()} events
                  </StatusPill>
                </div>
                <p className="text-sm text-slate-700">
                  Every event hashes to the next. No tampering detected.
                </p>
              </div>
            </>
          ) : (
            <>
              <ShieldAlert
                className="size-6 shrink-0 text-status-frozen"
                aria-hidden
              />
              <div className="flex-1 space-y-2">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <p className="font-serif text-lg font-semibold text-slate-900">
                    Chain broken
                  </p>
                  <StatusPill kind="frozen">
                    Seq {report.first_corrupt_seq}
                  </StatusPill>
                </div>
                <p className="text-sm text-slate-700">{report.reason}</p>
              </div>
            </>
          )}
        </section>
      )}

      <AnchorTimeline districtId={districtId} />
    </div>
  );
}
