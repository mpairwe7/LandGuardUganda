"use client";

/**
 * FraudExplainer — the AI-screening result, never the decision.
 *
 * Design rules from the AI Ethics Charter:
 *   - Lead with WHAT FIRED, in plain English.
 *   - Risk score is a number, never a meter — comparable across cases.
 *   - Orange for ML-flagged (status-flag); red is reserved for human-affirmed.
 *   - The disclaimer is fixed copy and never optional.
 */

import { AlertOctagon, AlertTriangle, ShieldCheck } from "lucide-react";

interface Signal {
  name: string;
  weight: number;
  score: number;
  explanation: string;
}

interface Props {
  riskScore: number;
  recommendedAction: "NONE" | "FLAG" | "BLOCK";
  signals: Signal[];
}

const LABELS: Record<string, string> = {
  geometry_overlap: "Boundary overlap detected",
  rapid_retransfer: "Rapid re-transfer pattern",
  nin_reuse: "National ID reuse",
  size_anomaly: "Parcel size outside district norm",
  watchlist_name: "Watchlist match",
  consideration_anomaly: "Unusual consideration price",
  nira_kyc: "KYC not verified at NIRA",
};

export function FraudExplainer({ riskScore, recommendedAction, signals }: Props) {
  const surface =
    recommendedAction === "BLOCK"
      ? "state-flag bg-orange-50/40"
      : recommendedAction === "FLAG"
        ? "state-pending bg-amber-50/40"
        : "state-verified bg-emerald-50/30";

  const Icon =
    recommendedAction === "BLOCK"
      ? AlertOctagon
      : recommendedAction === "FLAG"
        ? AlertTriangle
        : ShieldCheck;

  const headline =
    recommendedAction === "BLOCK"
      ? "Strong fraud signals — human review required before any state change."
      : recommendedAction === "FLAG"
        ? "Anomaly signals detected — please review."
        : "No fraud signals fired. This transfer looks clean.";

  return (
    <section className={`card-surface ${surface}`}>
      <header className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Icon
            className={
              recommendedAction === "BLOCK"
                ? "size-6 shrink-0 text-status-flag"
                : recommendedAction === "FLAG"
                  ? "size-6 shrink-0 text-status-pending"
                  : "size-6 shrink-0 text-status-verified"
            }
          />
          <div>
            <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
              AI screening result
            </p>
            <h3 className="text-lg font-semibold text-slate-900">{headline}</h3>
          </div>
        </div>
        <RiskNumber score={riskScore} action={recommendedAction} />
      </header>

      {signals.length > 0 && (
        <ul className="mt-5 space-y-2">
          {signals.map((s) => (
            <li
              key={s.name}
              className="flex items-start gap-3 rounded-md border border-slate-200 bg-white px-3 py-2.5"
            >
              <span className="inline-flex h-6 min-w-[2rem] items-center justify-center rounded bg-slate-100 px-1.5 text-[11px] font-semibold tabular-nums text-slate-700">
                +{s.weight}
              </span>
              <div className="flex-1 text-sm">
                <p className="font-medium text-slate-900">{LABELS[s.name] ?? s.name}</p>
                <p className="text-slate-600">{s.explanation}</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-5 border-t border-slate-200 pt-3 text-xs text-slate-500">
        This is a decision-support indicator. <strong>No parcel is frozen</strong>{" "}
        without affirmative action by a LAND_OFFICER or REGISTRAR. Citizens
        affected by a flag may appeal at any District Land Office or via USSD{" "}
        <span className="font-mono">*247*256*9#</span>.
      </p>
    </section>
  );
}

function RiskNumber({ score, action }: { score: number; action: "NONE" | "FLAG" | "BLOCK" }) {
  const color =
    action === "BLOCK"
      ? "text-status-flag"
      : action === "FLAG"
        ? "text-status-pending"
        : "text-status-verified";
  return (
    <div className={`flex items-baseline gap-1 ${color}`}>
      <span className="text-3xl font-bold tabular-nums leading-none">{score}</span>
      <span className="text-xs font-medium uppercase tracking-wider">/100 · {action}</span>
    </div>
  );
}
