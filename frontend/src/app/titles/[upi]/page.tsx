"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Printer, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { TitleCertificate } from "@/components/certificate/TitleCertificate";
import { Button } from "@/components/common/Button";

interface TitleResponse {
  title_no: string;
  parcel_id: string;
  issued_at: number;
  registrar_id: string;
  district_id: number;
  content_hash: string;
  tx_hash: string | null;
  block_number: number | null;
  anchor_status: string;
}

/**
 * Title certificate viewer. The certificate component owns its own visual
 * presentation (A4, watermark, seal); this page just provides the print
 * action and handles loading / not-found states.
 */
export default function TitlePage() {
  const params = useParams<{ upi: string }>();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["title", params.upi],
    queryFn: () =>
      api.get<TitleResponse>(
        `/v1/titles/${encodeURIComponent(params.upi)}`,
      ),
    staleTime: 5 * 60_000,
  });

  if (isLoading) {
    return (
      <main className="mx-auto max-w-citizen px-6 py-10">
        <p className="text-sm text-slate-500">Loading title…</p>
      </main>
    );
  }
  if (isError || !data) {
    return (
      <main className="mx-auto max-w-citizen px-6 py-10">
        <div className="card-surface state-frozen flex items-start gap-4">
          <ShieldAlert
            className="size-6 shrink-0 text-status-frozen"
            aria-hidden
          />
          <div>
            <p className="font-serif text-lg font-semibold text-slate-900">
              Title not found
            </p>
            <p className="mt-1 text-sm text-slate-700">
              We could not find this title in any district ledger. Check the
              title number for transcription errors.
            </p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <TitleCertificate title={data} />
      <div className="no-print mt-6 flex items-center justify-end gap-3">
        <p className="text-xs text-slate-500">
          Print on A4 portrait, 100% scale. The QR remains verifiable on
          paper.
        </p>
        <Button
          variant="primary"
          icon={<Printer className="size-4" />}
          onClick={() => window.print()}
        >
          Print certificate
        </Button>
      </div>
    </main>
  );
}
