// Cross-language parity test for frontend/src/lib/merkle.ts.
//
// Loads the canonical fixture emitted by backend/scripts/emit_merkle_vectors.py
// (and consumed identically by contracts/test/MerkleParity.t.sol). For every
// case the TS verifier must produce the same roots and accept the same proofs
// the Python reference generated — otherwise the cross-language byte-for-byte
// parity claim (Public Claim 2) silently fails in the field.

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  computeMerkleRoot,
  keccakHex,
  pairHash,
  sha256Hex,
  verifyMerkleProof,
  verifyMerkleProofEvm,
} from "@/lib/merkle";

interface ProofSha256 {
  index: number;
  leaf: string;
  siblings: string[];
  root: string;
}

interface ProofEvm {
  index: number;
  leaf: string;
  siblings: string[];
  root: string;
}

interface ParityCase {
  name: string;
  inputs: string[];
  sha256: { leaves: string[]; root: string; proofs: ProofSha256[] };
  evm: { leaves: string[]; root: string; proofs: ProofEvm[] };
  skip_solidity: boolean;
  _comment?: string;
}

interface ParityFixture {
  schema_version: number;
  regimes: string[];
  cases: ParityCase[];
}

const FIXTURE_PATH = path.resolve(
  __dirname,
  "../../../contracts/test/merkle-parity.json",
);

function loadFixture(): ParityFixture {
  const raw = readFileSync(FIXTURE_PATH, "utf-8");
  const parsed = JSON.parse(raw) as ParityFixture;
  if (parsed.schema_version !== 1) {
    throw new Error(
      `unexpected merkle-parity.json schema_version ${parsed.schema_version}; regenerate via backend/scripts/emit_merkle_vectors.py`,
    );
  }
  return parsed;
}

const fixture = loadFixture();

describe("merkle parity fixture metadata", () => {
  it("declares both regimes", () => {
    expect(fixture.regimes).toEqual([
      "sha256_index_ordered",
      "keccak_sorted_pair",
    ]);
  });

  it("contains at least 8 cases", () => {
    expect(fixture.cases.length).toBeGreaterThanOrEqual(8);
  });
});

describe.each(fixture.cases)("parity case: $name", (testCase) => {
  it("matches the Python SHA-256 leaf hashes", () => {
    const tsLeaves = testCase.inputs.map(sha256Hex);
    expect(tsLeaves).toEqual(testCase.sha256.leaves);
  });

  it("matches the Python SHA-256 root", () => {
    const tsRoot = computeMerkleRoot(testCase.sha256.leaves);
    expect(tsRoot).toEqual(testCase.sha256.root);
  });

  it("verifies every SHA-256 proof from the fixture", () => {
    for (const proof of testCase.sha256.proofs) {
      expect(
        verifyMerkleProof(proof.leaf, proof.siblings, proof.root, proof.index),
      ).toBe(true);
    }
  });

  it("rejects every SHA-256 proof when the leaf is tampered", () => {
    for (const proof of testCase.sha256.proofs) {
      const tampered = pairHash(proof.leaf, "ff");
      expect(
        verifyMerkleProof(tampered, proof.siblings, proof.root, proof.index),
      ).toBe(false);
    }
  });

  it("matches the Python keccak-bridged leaves", () => {
    const tsKeccakLeaves = testCase.sha256.leaves.map((sha) => keccakHex(sha));
    expect(tsKeccakLeaves).toEqual(testCase.evm.leaves);
  });

  it("verifies every EVM proof against the on-chain-compatible root", () => {
    for (const proof of testCase.evm.proofs) {
      expect(
        verifyMerkleProofEvm(proof.leaf, proof.siblings, proof.root),
      ).toBe(true);
    }
  });

  it("rejects every EVM proof when the leaf is tampered", () => {
    if (testCase.evm.proofs.length === 0) return;
    for (const proof of testCase.evm.proofs) {
      const tampered = keccakHex("not-the-real-leaf");
      // Single-leaf trees have no siblings: the verifier compares leaf to root
      // directly, so tampering trivially fails. For multi-leaf trees the
      // tampered hash must propagate through ``keccakPairSorted`` and miss.
      expect(
        verifyMerkleProofEvm(tampered, proof.siblings, proof.root),
      ).toBe(false);
    }
  });
});
