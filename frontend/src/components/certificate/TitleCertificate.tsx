"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { formatTs, tenureLabel } from "@/lib/format";
import { HashDisplay } from "@/components/common/HashDisplay";
import { StatusPill } from "@/components/common/StatusPill";
import { CoatOfArmsMark } from "@/components/layout/CoatOfArmsMark";

interface TitleData {
  title_no: string;
  parcel_id: string;
  issued_at: number;
  registrar_id: string;
  district_id: number;
  content_hash: string;
  tx_hash: string | null;
  block_number: number | null;
  anchor_status: string;
  owner_full_name?: string;
  tenure_type?: string;
}

/**
 * Title certificate — government artefact.
 *
 * Visual grammar: A4 portrait, IBM Plex Serif heading, deep-green coat-of-arms
 * band, ration of gold reserved for the seal area. A barely-visible UPI hash
 * watermark across the page deters casual photocopy fraud. Print-optimised
 * via `print.css` and the `.print-page` class.
 */
export function TitleCertificate({ title }: { title: TitleData }) {
  const [qr, setQr] = useState<string | null>(null);

  useEffect(() => {
    const verifyUrl = `${typeof window === "undefined" ? "" : window.location.origin}/verify?title=${encodeURIComponent(
      title.title_no,
    )}`;
    QRCode.toDataURL(verifyUrl, {
      width: 240,
      margin: 0,
      errorCorrectionLevel: "M",
      color: { dark: "#08200d", light: "#ffffff" },
    }).then(setQr);
  }, [title.title_no]);

  const anchored = title.anchor_status === "CONFIRMED" || title.anchor_status === "ANCHORED";

  return (
    <article className="card-document document-watermark print-page relative mx-auto max-w-[210mm] font-sans text-slate-900">
      {/* HEADER BAND ----------------------------------------------------- */}
      <header className="-mx-10 -mt-10 mb-8 flex items-center gap-4 border-b-4 border-seal-400 bg-seal-50/60 px-10 py-4">
        <CoatOfArmsMark size={44} />
        <div className="flex-1">
          <p className="font-serif text-[11px] uppercase tracking-[0.22em] text-guard-700">
            Republic of Uganda
          </p>
          <p className="text-sm font-semibold text-guard-800">
            Ministry of Lands, Housing &amp; Urban Development
          </p>
          <p className="text-xs text-slate-600">
            Issued through LandGuard · Tamper-evident · Verifiable on public blockchain
          </p>
        </div>
        <div className="text-right">
          <p className="text-caption uppercase tracking-[0.18em] text-slate-500">Title No.</p>
          <p className="font-mono text-lg font-semibold text-slate-900">{title.title_no}</p>
        </div>
      </header>

      {/* DOCUMENT TITLE -------------------------------------------------- */}
      <h1 className="mb-1 text-center font-serif text-3xl font-bold tracking-tight text-slate-900">
        Certificate of Title
      </h1>
      <p className="mb-8 text-center text-sm text-slate-500">
        This certificate confirms the registration of the parcel below in the
        Mityana District ledger.
      </p>

      {/* DATA BLOCK ------------------------------------------------------ */}
      <dl className="mb-8 grid grid-cols-2 gap-x-10 gap-y-4">
        <DataRow label="Registered owner" value={title.owner_full_name ?? "—"} redactable />
        <DataRow label="Parcel UPI" value={<span className="font-mono">{title.parcel_id}</span>} />
        <DataRow label="Tenure" value={title.tenure_type ? tenureLabel(title.tenure_type) : "—"} />
        <DataRow label="District code" value={String(title.district_id)} />
        <DataRow label="Date of issue" value={formatTs(title.issued_at)} />
        <DataRow label="Registrar" value={<span className="redactable">{title.registrar_id}</span>} />
      </dl>

      {/* SEAL AREA ------------------------------------------------------- */}
      <div className="mb-6 flex items-end gap-8 border-t border-slate-200 pt-6">
        <div className="flex-1 space-y-2 text-xs text-slate-600">
          <p className="font-semibold uppercase tracking-wider text-slate-700">
            Public verification
          </p>
          <p>
            Scan the QR or visit{" "}
            <span className="font-mono">landguard.ug/verify</span> · USSD{" "}
            <span className="font-mono">*247*256#</span>
          </p>
          <p>
            Anchored to a public blockchain. Any modification to this
            certificate breaks the Merkle proof and the document fails
            verification.
          </p>
        </div>
        <div className="relative flex h-[140px] w-[140px] items-center justify-center rounded-full border-4 border-seal-400 bg-white">
          {qr ? (
            <img src={qr} alt="QR verification code" className="size-[112px]" />
          ) : (
            <div className="size-[112px] animate-pulse rounded bg-slate-100" />
          )}
          <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 rounded bg-white px-2 text-[9px] font-semibold uppercase tracking-widest text-seal-700">
            Official Seal
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-slate-200 pt-3">
        {anchored ? (
          <StatusPill kind="verified">
            Anchored · block {title.block_number ?? "—"}
          </StatusPill>
        ) : (
          <StatusPill kind="pending">
            Anchor pending — legally valid off-chain
          </StatusPill>
        )}
        <p className="text-[10px] text-slate-400">
          Generated by LandGuard Uganda · {new Date().toISOString().slice(0, 10)}
        </p>
      </div>

      {/* FOOTER BAND ----------------------------------------------------- */}
      <footer className="-mx-10 -mb-10 mt-6 grid grid-cols-2 gap-4 border-t border-slate-200 bg-slate-50/60 px-10 py-3 text-[10px] text-slate-600">
        <div>
          <p className="font-semibold uppercase tracking-wider text-slate-700">
            Content hash (SHA-256)
          </p>
          <HashDisplay value={title.content_hash} head={14} tail={10} copy={false} />
        </div>
        <div>
          <p className="font-semibold uppercase tracking-wider text-slate-700">
            Anchor transaction
          </p>
          <HashDisplay value={title.tx_hash} head={14} tail={10} copy={false} />
        </div>
      </footer>
    </article>
  );
}

function DataRow({
  label,
  value,
  redactable,
}: {
  label: string;
  value: React.ReactNode;
  redactable?: boolean;
}) {
  return (
    <div className="border-b border-slate-100 pb-2">
      <dt className="text-caption uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className={`mt-1 text-base font-medium text-slate-900 ${redactable ? "redactable" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
