"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileCheck2, Anchor } from "lucide-react";
import { api, makeIdempotencyKey } from "@/lib/api";
import { MerkleProofVisualizer } from "@/components/chain/MerkleProofVisualizer";
import { Button } from "@/components/common/Button";

interface TitleResponse {
  title_no: string;
  parcel_id: string;
  content_hash: string;
  district_id: number;
  tx_hash: string | null;
  block_number: number | null;
  anchor_status: string;
  merkle_proof: { leaf: string; siblings: string[]; root: string } | null;
}

/**
 * Registrar console — the title-issuance surface. Used live during Act 2 of
 * the showcase: a parcel UPI in, a title out, a Merkle proof animated, and
 * the next anchor batch scheduled.
 */
export default function RegistrarPage() {
  const [parcelId, setParcelId] = useState("UG-MIT-024718/2026");
  const [ownerId, setOwnerId] = useState("");
  const [issued, setIssued] = useState<TitleResponse | null>(null);

  const issue = useMutation({
    mutationFn: () =>
      api.post<TitleResponse>(
        "/v1/titles/issue",
        { parcel_id: parcelId, owner_id: ownerId },
        makeIdempotencyKey(),
      ),
    onSuccess: (data) => {
      setIssued(data);
      toast.success(`Title ${data.title_no} issued.`);
    },
    onError: (err) =>
      toast.error(`Could not issue: ${(err as { detail?: string }).detail ?? "error"}`),
  });

  const flush = useMutation({
    mutationFn: () => api.post(`/v1/anchors/flush/3`, undefined, makeIdempotencyKey()),
    onSuccess: () => toast.success("Anchor flush triggered."),
  });

  return (
    <div className="mx-auto max-w-citizen space-y-6">
      <header className="border-b border-slate-200 pb-4">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Registrar console
        </p>
        <h1 className="font-serif text-2xl font-bold text-slate-900">
          Issue title
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Issues a title certificate, appends a{" "}
          <code className="font-mono text-slate-800">TITLE_ISSUED</code> event
          to the district ledger, and schedules the next on-chain anchor. The
          Merkle inclusion proof is materialised on demand from the audit chain.
        </p>
      </header>

      <section className="card-surface space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1.5">
            <span className="field-label">Parcel UPI</span>
            <input
              value={parcelId}
              onChange={(e) => setParcelId(e.target.value.toUpperCase())}
              className="field-input-mono"
              placeholder="UG-DDD-NNNNNN/YYYY"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="field-label">Owner UUID</span>
            <input
              value={ownerId}
              onChange={(e) => setOwnerId(e.target.value)}
              className="field-input-mono redactable"
              placeholder="00000000-0000-0000-0000-000000000000"
            />
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4">
          <Button
            variant="primary"
            icon={<FileCheck2 className="size-4" />}
            onClick={() => issue.mutate()}
            disabled={!parcelId || !ownerId}
            loading={issue.isPending}
          >
            Issue title
          </Button>
          <Button
            variant="secondary"
            icon={<Anchor className="size-4" />}
            onClick={() => flush.mutate()}
            loading={flush.isPending}
          >
            Flush anchor now
          </Button>
          <span className="ml-auto text-xs text-slate-500">
            Issuance is audited and idempotent on the request key.
          </span>
        </div>
      </section>

      {issued?.merkle_proof && (
        <MerkleProofVisualizer
          leaf={issued.merkle_proof.leaf}
          siblings={issued.merkle_proof.siblings}
          root={issued.merkle_proof.root}
          txHash={issued.tx_hash}
          blockNumber={issued.block_number}
          status={issued.anchor_status}
        />
      )}
    </div>
  );
}
