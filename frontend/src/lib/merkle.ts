// Pure-TS Merkle verification — mirrors backend/app/audit/merkle.py and
// contracts/src/LandRegistryAnchor.sol byte-for-byte.
//
// LandGuard runs two parallel trees:
//
//   1. Off-chain integrity tree — index-ordered SHA-256 (for audit chain
//      verifier, used in tests and offline auditing).
//   2. On-chain anchored tree — sorted-pair Keccak-256 over
//      keccak(sha256_hex_leaf) leaves (matches LandRegistryAnchor.verifyProof).
//
// Cross-checked via __tests__/lib/merkle.test.ts against shared test vectors.

import { createHash, createHmac } from "crypto";
import { keccak_256 } from "@noble/hashes/sha3";

// ---------------------------------------------------------------------------
// Off-chain (SHA-256) — Bitcoin-style index-ordered
// ---------------------------------------------------------------------------

export function sha256Hex(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

export function pairHash(left: string, right: string): string {
  return sha256Hex(left + right);
}

export function computeMerkleRoot(leafHashes: string[]): string {
  if (leafHashes.length === 0) return "";
  let level = [...leafHashes];
  while (level.length > 1) {
    if (level.length % 2 === 1) level.push(level[level.length - 1]!);
    const next: string[] = [];
    for (let i = 0; i < level.length; i += 2) {
      next.push(pairHash(level[i]!, level[i + 1]!));
    }
    level = next;
  }
  return level[0]!;
}

export function verifyMerkleProof(
  leaf: string,
  proof: string[],
  root: string,
  index: number,
): boolean {
  let h = leaf;
  let idx = index;
  for (const sibling of proof) {
    h = idx & 1 ? pairHash(sibling, h) : pairHash(h, sibling);
    idx = Math.floor(idx / 2);
  }
  return h === root;
}

// ---------------------------------------------------------------------------
// On-chain (Keccak-256, sorted-pair) — matches LandRegistryAnchor.verifyProof
// ---------------------------------------------------------------------------

function stripHex(value: string): string {
  return value.toLowerCase().replace(/^0x/, "");
}

function hexToBytes32(value: string): Uint8Array {
  let s = stripHex(value);
  if (s.length < 64) s = s.padStart(64, "0");
  else if (s.length > 64) s = s.slice(-64);
  const out = new Uint8Array(32);
  for (let i = 0; i < 32; i++) {
    out[i] = parseInt(s.substring(i * 2, i * 2 + 2), 16);
  }
  return out;
}

function bytesToHex(bytes: Uint8Array): string {
  return (
    "0x" +
    Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("")
  );
}

function compareBytes(a: Uint8Array, b: Uint8Array): number {
  for (let i = 0; i < 32; i++) {
    if (a[i]! < b[i]!) return -1;
    if (a[i]! > b[i]!) return 1;
  }
  return 0;
}

export function keccakHex(input: string | Uint8Array): string {
  const bytes = typeof input === "string" ? new TextEncoder().encode(input) : input;
  return "0x" + Buffer.from(keccak_256(bytes)).toString("hex");
}

export function keccakPairSorted(leftHex: string, rightHex: string): string {
  const a = hexToBytes32(leftHex);
  const b = hexToBytes32(rightHex);
  const [lo, hi] = compareBytes(a, b) <= 0 ? [a, b] : [b, a];
  const combined = new Uint8Array(64);
  combined.set(lo, 0);
  combined.set(hi, 32);
  return bytesToHex(keccak_256(combined));
}

/**
 * Verify a sorted-pair keccak proof against the on-chain anchored root.
 *
 * The leaf must already be in `keccak(sha256_hex_leaf)` form (which is what
 * the public verifier endpoint and printed title QR codes return). Use this
 * for offline verification when the chain is unreachable but the citizen
 * has a printed proof + the trusted root from a previous chain reading.
 */
export function verifyMerkleProofEvm(
  leafHex: string,
  siblings: string[],
  rootHex: string,
): boolean {
  let h = leafHex;
  for (const sibling of siblings) {
    h = keccakPairSorted(h, sibling);
  }
  return h.toLowerCase() === rootHex.toLowerCase();
}
