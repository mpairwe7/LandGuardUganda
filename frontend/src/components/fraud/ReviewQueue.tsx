"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertOctagon, CheckCircle2, ShieldOff } from "lucide-react";
import { api, makeIdempotencyKey } from "@/lib/api";
import { FraudExplainer } from "@/components/fraud/FraudExplainer";
import { Button } from "@/components/common/Button";
import { StatusPill } from "@/components/common/StatusPill";

interface ReviewItem {
  id: string;
  subject_type: string;
  subject_id: string;
  risk_score: number;
  recommended_action: "FLAG" | "BLOCK";
  signals: { name: string; weight: number; score: number; explanation: string }[];
  state: string;
  created_at: number;
  scorer_version: string;
}

/**
 * Officer review queue — the human-in-the-loop surface.
 *
 * Visual rule: only red ink (destructive button) when an officer commits a
 * freeze. Orange ink belongs to the AI-screening card. Notes are required
 * (≥4 chars) and persist to the audit chain.
 */
export function ReviewQueue({ districtId }: { districtId: number }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["fraud", "reviews", districtId],
    queryFn: () =>
      api.get<ReviewItem[]>(
        `/v1/fraud/reviews?district_id=${districtId}&state=PENDING_REVIEW`,
      ),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  return (
    <section className="space-y-4">
      <header className="flex items-start justify-between gap-4 border-b border-slate-200 pb-3">
        <div>
          <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
            Officer console
          </p>
          <h2 className="text-xl font-semibold text-slate-900">
            Pending human review
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            AI alerts queued for officer judgement.{" "}
            <strong className="text-slate-900">
              No parcel is frozen until a human affirms.
            </strong>{" "}
            All decisions are written to the tamper-evident audit chain. See the
            AI Ethics Charter.
          </p>
        </div>
        {data && data.length > 0 && (
          <StatusPill kind="flag">
            {data.length} awaiting review
          </StatusPill>
        )}
      </header>

      {isLoading && (
        <p className="text-sm text-slate-500">Loading queue…</p>
      )}

      <ul className="space-y-6" role="list">
        {data?.map((item) => (
          <ReviewCard
            key={item.id}
            item={item}
            onResolved={() =>
              qc.invalidateQueries({ queryKey: ["fraud", "reviews"] })
            }
          />
        ))}
        {!isLoading && (!data || data.length === 0) && (
          <li className="card-surface state-verified text-sm text-slate-600">
            No pending reviews. The queue is clean.
          </li>
        )}
      </ul>
    </section>
  );
}

function ReviewCard({
  item,
  onResolved,
}: {
  item: ReviewItem;
  onResolved: () => void;
}) {
  const [notes, setNotes] = useState("");
  const affirm = useMutation({
    mutationFn: () =>
      api.post(
        `/v1/fraud/review/${item.id}/affirm`,
        { notes },
        makeIdempotencyKey(),
      ),
    onSuccess: () => {
      toast.success("Alert affirmed. Parcel frozen pending dispute resolution.");
      onResolved();
    },
    onError: (err) =>
      toast.error(`Affirm failed: ${(err as { detail?: string }).detail}`),
  });
  const dismiss = useMutation({
    mutationFn: () =>
      api.post(
        `/v1/fraud/review/${item.id}/dismiss`,
        { notes },
        makeIdempotencyKey(),
      ),
    onSuccess: () => {
      toast.success("Alert dismissed as false positive.");
      onResolved();
    },
    onError: (err) =>
      toast.error(`Dismiss failed: ${(err as { detail?: string }).detail}`),
  });

  const tooShort = notes.length < 4;
  const busy = affirm.isPending || dismiss.isPending;

  return (
    <li className="space-y-3">
      <FraudExplainer
        riskScore={item.risk_score}
        recommendedAction={item.recommended_action}
        signals={item.signals}
      />

      <div className="card-surface space-y-4">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption uppercase tracking-wider text-slate-500">
          <AlertOctagon className="size-4 text-status-flag" aria-hidden />
          <span className="text-slate-700">{item.subject_type}</span>
          <span className="text-slate-400">·</span>
          <code className="font-mono text-slate-700 normal-case tracking-normal redactable">
            {item.subject_id}
          </code>
          <span className="text-slate-400">·</span>
          <span>scorer</span>
          <code className="font-mono text-slate-700 normal-case tracking-normal">
            {item.scorer_version}
          </code>
        </header>

        <label className="block space-y-1.5">
          <span className="field-label">Officer decision notes</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Required (≥4 chars). E.g. 'Confirmed forgery — buyer ID does not match NIRA photo.'"
            rows={3}
            className="field-input redactable"
          />
          <span className="field-help">
            Notes are persisted to the audit chain alongside your user id and
            cannot be edited after submission.
          </span>
        </label>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="destructive"
            onClick={() => affirm.mutate()}
            disabled={tooShort || busy}
            loading={affirm.isPending}
            icon={<AlertOctagon className="size-4" />}
          >
            Affirm — freeze parcel
          </Button>
          <Button
            variant="secondary"
            onClick={() => dismiss.mutate()}
            disabled={tooShort || busy}
            loading={dismiss.isPending}
            icon={<CheckCircle2 className="size-4" />}
          >
            Dismiss — false positive
          </Button>
          {tooShort && (
            <span className="inline-flex items-center gap-1 text-xs text-slate-500">
              <ShieldOff className="size-3.5" aria-hidden />
              Enter notes to enable actions
            </span>
          )}
        </div>

        <p className="border-t border-slate-200 pt-3 text-xs text-slate-500">
          Per the AI Ethics Charter: only human affirmation freezes a parcel.
          An affirmed freeze opens a citizen-appealable dispute and emits an{" "}
          <code className="font-mono">OWNERSHIP_FROZEN</code> event on the
          per-district audit chain.
        </p>
      </div>
    </li>
  );
}
