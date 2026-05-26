"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert, ScanLine, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { useLocale } from "@/lib/i18n/useLocale";
import { MerkleProofVisualizer } from "@/components/chain/MerkleProofVisualizer";
import { QrScanner } from "@/components/verify/QrScanner";
import { Button } from "@/components/common/Button";
import { StatusPill } from "@/components/common/StatusPill";
import { HashDisplay } from "@/components/common/HashDisplay";

interface VerifyResponse {
  valid: boolean;
  title_no: string | null;
  anchor_status: string;
  anchored_at: number | null;
  batch_id: string | null;
  tx_hash: string | null;
  block_number: number | null;
  chain_id: number | null;
  reason: string | null;
}

/**
 * Public verifier — the showcase moment (Acts 1 and 4).
 *
 * Design rules: one question per screen ("Is this title valid?"). The
 * verdict is iconic + colour + plain language. Receipts (block, tx, batch)
 * sit beneath the verdict for journalists and NGO workers. No login,
 * no chrome beyond the ministry attribution band.
 */
export default function VerifyPage() {
  const { t } = useLocale();
  const params = useSearchParams();
  const initial = params.get("title") ?? "";
  const [titleNo, setTitleNo] = useState(initial);
  const [showScanner, setShowScanner] = useState(false);
  const [proof, setProof] = useState<{
    leaf: string;
    siblings: string[];
    root: string;
  } | null>(null);

  const verify = useMutation({
    mutationFn: (t: string) =>
      api.post<VerifyResponse>("/v1/verify/title", { title_no: t }),
  });

  useEffect(() => {
    if (initial) verify.mutate(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  const fetchProof = async (t: string) => {
    try {
      const p = await api.get<{
        leaf: string;
        siblings: string[];
        root: string;
      }>(`/v1/anchors/title/${encodeURIComponent(t)}/proof`);
      setProof(p);
    } catch {
      setProof(null);
    }
  };

  return (
    <div className="mx-auto max-w-citizen space-y-8">
      <header className="space-y-2">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          {t("verify.eyebrow")}
        </p>
        <h1 className="font-serif text-3xl font-bold text-slate-900">
          {t("verify.title")}
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-slate-600">
          {t("verify.subtitle")}
        </p>
      </header>

      <section className="card-elevated space-y-4">
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (titleNo) {
              verify.mutate(titleNo);
              fetchProof(titleNo);
            }
          }}
        >
          <input
            type="text"
            placeholder={t("verify.input.placeholder")}
            className="field-input-mono flex-1"
            value={titleNo}
            onChange={(e) =>
              setTitleNo(e.target.value.toUpperCase().trim())
            }
            aria-label={t("verify.input.label")}
          />
          <Button
            type="submit"
            variant="primary"
            disabled={!titleNo}
            loading={verify.isPending}
            icon={<ArrowRight className="size-4" />}
          >
            {t("verify.button.verify")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            icon={<ScanLine className="size-4" />}
            onClick={() => setShowScanner((v) => !v)}
          >
            {showScanner ? t("verify.button.scan_close") : t("verify.button.scan")}
          </Button>
        </form>
        {showScanner && (
          <div className="border-t border-slate-200 pt-4">
            <QrScanner
              onResult={(t) => {
                setTitleNo(t);
                setShowScanner(false);
                verify.mutate(t);
                fetchProof(t);
              }}
            />
          </div>
        )}
        <p className="text-xs text-slate-500">
          {t("verify.ussd_hint.before")}
          <span className="font-mono text-slate-800">*247*256#</span>
          {t("verify.ussd_hint.after")}
        </p>
      </section>

      {verify.data && <ResultPanel response={verify.data} proof={proof} />}

      {verify.isError && (
        <div className="card-surface state-frozen flex items-start gap-4">
          <ShieldAlert
            className="size-6 shrink-0 text-status-frozen"
            aria-hidden
          />
          <div>
            <p className="font-serif text-lg font-semibold text-slate-900">
              {t("verify.error.title")}
            </p>
            <p className="mt-1 text-sm text-slate-700">
              {(verify.error as { detail?: string }).detail ??
                t("verify.error.body_default")}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function ResultPanel({
  response,
  proof,
}: {
  response: VerifyResponse;
  proof: { leaf: string; siblings: string[]; root: string } | null;
}) {
  const { t } = useLocale();
  if (response.valid) {
    return (
      <div className="space-y-5">
        <div className="card-surface state-verified flex items-start gap-4">
          <ShieldCheck
            className="size-7 shrink-0 text-status-verified"
            aria-hidden
          />
          <div className="flex-1 space-y-2">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <p className="font-serif text-xl font-semibold text-slate-900">
                {t("verify.result.verified.title")}
              </p>
              <StatusPill kind="verified">
                {response.anchor_status === "CONFIRMED"
                  ? t("verify.result.verified.confirmed")
                  : t("verify.result.verified.anchored")}
              </StatusPill>
            </div>
            <p className="text-sm text-slate-700">
              {t("verify.result.verified.body")}
            </p>
            <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
              <Receipt
                label={t("verify.receipt.title")}
                value={
                  <span className="font-mono text-slate-900">
                    {response.title_no}
                  </span>
                }
              />
              <Receipt
                label={t("verify.receipt.batch")}
                value={
                  <HashDisplay
                    value={response.batch_id}
                    head={8}
                    tail={6}
                    copy={false}
                  />
                }
              />
              <Receipt
                label={t("verify.receipt.chain")}
                value={
                  <span className="font-mono text-slate-900 tabular-nums">
                    {response.chain_id ?? "—"}
                  </span>
                }
              />
              <Receipt
                label={t("verify.receipt.block")}
                value={
                  <span className="font-mono text-slate-900 tabular-nums">
                    {response.block_number ?? "—"}
                  </span>
                }
              />
            </dl>
          </div>
        </div>
        {proof && (
          <MerkleProofVisualizer
            leaf={proof.leaf}
            siblings={proof.siblings}
            root={proof.root}
            txHash={response.tx_hash}
            blockNumber={response.block_number}
            chainId={response.chain_id}
            status={response.anchor_status}
          />
        )}
      </div>
    );
  }

  const isPending = response.reason === "title_pending_anchor";
  return (
    <div
      className={`card-surface flex items-start gap-4 ${
        isPending ? "state-pending" : "state-frozen"
      }`}
    >
      <ShieldAlert
        className={`size-7 shrink-0 ${isPending ? "text-status-pending" : "text-status-frozen"}`}
        aria-hidden
      />
      <div className="flex-1 space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <p className="font-serif text-xl font-semibold text-slate-900">
            {isPending
              ? t("verify.result.pending.title")
              : t("verify.result.failed.title")}
          </p>
          <StatusPill kind={isPending ? "pending" : "frozen"}>
            {isPending
              ? t("verify.result.pending.label")
              : t("verify.result.failed.label")}
          </StatusPill>
        </div>
        <p className="text-sm leading-relaxed text-slate-700">
          {response.reason === "title_pending_anchor"
            ? t("verify.result.pending.body")
            : response.reason === "title_not_found"
              ? t("verify.result.notfound.body")
              : (response.reason ?? t("verify.error.title"))}
        </p>
      </div>
    </div>
  );
}

function Receipt({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-caption uppercase tracking-wider text-slate-500">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
    </div>
  );
}
