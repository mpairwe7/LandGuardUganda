"use client";

/**
 * MerkleProofVisualizer — the showcase moment.
 *
 * Design intent: government-formal cryptography. Solid lines, no gradients,
 * no glow, no neon. The root node is the only gold-filled element; the rest
 * is forest green + slate. Animation completes in ≤900ms; it does not loop.
 *
 * Reads byte-identically to LandRegistryAnchor.verifyProof (sorted-pair
 * keccak); see docs/adr/0001-dual-merkle-regime.md.
 */

import { motion } from "framer-motion";
import { useMemo } from "react";
import { ShieldCheck } from "lucide-react";
import { HashDisplay } from "@/components/common/HashDisplay";
import { StatusPill } from "@/components/common/StatusPill";

interface Props {
  leaf: string;
  siblings: string[];
  root: string;
  txHash?: string | null;
  blockNumber?: number | null;
  chainId?: number | null;
  status?: string;
}

interface Node {
  label: string;
  hex: string;
  level: "leaf" | "sibling" | "root";
}

export function MerkleProofVisualizer({
  leaf,
  siblings,
  root,
  txHash,
  blockNumber,
  chainId,
  status = "CONFIRMED",
}: Props) {
  const nodes = useMemo<Node[]>(() => {
    const out: Node[] = [{ label: "leaf", hex: leaf, level: "leaf" }];
    siblings.forEach((s, i) =>
      out.push({ label: `sibling L${i}`, hex: s, level: "sibling" }),
    );
    out.push({ label: "root", hex: root, level: "root" });
    return out;
  }, [leaf, siblings, root]);

  const isAnchored = status === "CONFIRMED" || status === "ANCHORED";

  return (
    <section className="card-elevated">
      <header className="mb-5 flex items-center justify-between border-b border-slate-200 pb-3">
        <div>
          <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
            Cryptographic inclusion proof
          </p>
          <h3 className="text-lg font-semibold text-slate-900">
            Merkle path → on-chain root
          </h3>
        </div>
        {isAnchored ? (
          <StatusPill kind="verified">
            {status === "CONFIRMED" ? "Confirmed on chain" : "Anchored"}
          </StatusPill>
        ) : (
          <StatusPill kind="pending">{status}</StatusPill>
        )}
      </header>

      <ol className="space-y-2" role="list">
        {nodes.map((n, i) => (
          <motion.li
            key={`${n.label}-${i}`}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.07, duration: 0.32, ease: "easeOut" }}
            className="grid grid-cols-[5.5rem_1fr] items-center gap-2 rounded-md border border-slate-100 bg-slate-50/60 px-3 py-2 sm:grid-cols-[7rem_1fr_auto] sm:gap-3"
          >
            <span
              className={
                n.level === "root"
                  ? "text-xs font-semibold uppercase tracking-wider text-seal-700"
                  : "text-xs font-medium uppercase tracking-wider text-slate-500"
              }
            >
              {n.label}
            </span>
            <HashDisplay value={n.hex} head={10} tail={8} copy={false} />
            {n.level === "root" && (
              <motion.span
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{
                  delay: nodes.length * 0.07,
                  duration: 0.28,
                  type: "spring",
                  stiffness: 280,
                }}
                className="inline-flex items-center gap-1.5 rounded-md border border-seal-300 bg-seal-50 px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-seal-700"
              >
                <ShieldCheck className="size-3.5" />
                On chain
              </motion.span>
            )}
          </motion.li>
        ))}
      </ol>

      {(txHash || blockNumber || chainId) && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: nodes.length * 0.07 + 0.18, duration: 0.36 }}
          className="mt-5 grid grid-cols-3 gap-4 border-t border-slate-200 pt-4"
        >
          <Field
            label="Transaction"
            value={<HashDisplay value={txHash ?? null} head={8} tail={6} />}
          />
          <Field
            label="Block"
            value={<span className="font-mono text-sm tabular-nums">{blockNumber ?? "—"}</span>}
          />
          <Field
            label="Chain ID"
            value={<span className="font-mono text-sm tabular-nums">{chainId ?? "—"}</span>}
          />
        </motion.div>
      )}
    </section>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-caption uppercase tracking-wider text-slate-500">{label}</p>
      <div className="mt-0.5">{value}</div>
    </div>
  );
}
