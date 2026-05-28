// Unit tests for the TypeScript Merkle verifier (frontend/src/lib/merkle.ts).
//
// These tests pin the behaviour of each exported function in isolation. They
// do NOT cross-check against Python or Solidity — that's merkle.parity.test.ts.
// Run with: `cd frontend && bun run test merkle`.

import { describe, expect, it } from "vitest";

import {
  computeMerkleRoot,
  keccakHex,
  keccakPairSorted,
  pairHash,
  sha256Hex,
  verifyMerkleProof,
  verifyMerkleProofEvm,
} from "@/lib/merkle";

describe("sha256Hex", () => {
  it("matches the canonical empty-string digest", () => {
    expect(sha256Hex("")).toBe(
      "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    );
  });

  it("produces a 64-char lowercase hex output", () => {
    const h = sha256Hex("anything");
    expect(h).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe("pairHash", () => {
  it("is sensitive to argument order (index-ordered regime)", () => {
    const a = sha256Hex("a");
    const b = sha256Hex("b");
    expect(pairHash(a, b)).not.toBe(pairHash(b, a));
  });
});

describe("computeMerkleRoot (SHA-256 index-ordered)", () => {
  it("returns the empty string for empty input", () => {
    expect(computeMerkleRoot([])).toBe("");
  });

  it("returns the leaf itself for a single-leaf tree", () => {
    const leaf = sha256Hex("only");
    expect(computeMerkleRoot([leaf])).toBe(leaf);
  });

  it("uses duplicate-last semantics for odd leaf counts", () => {
    const a = sha256Hex("a");
    const b = sha256Hex("b");
    const c = sha256Hex("c");
    // Three leaves: ab = pairHash(a,b); cc = pairHash(c,c); root = pairHash(ab,cc).
    const ab = pairHash(a, b);
    const cc = pairHash(c, c);
    const expected = pairHash(ab, cc);
    expect(computeMerkleRoot([a, b, c])).toBe(expected);
  });
});

describe("verifyMerkleProof (SHA-256 index-ordered)", () => {
  it("accepts a valid proof and rejects a tampered leaf", () => {
    const leaves = ["a", "b", "c", "d"].map(sha256Hex);
    const root = computeMerkleRoot(leaves);
    // Proof for index 0: sibling=leaves[1] at level 0, sibling=pairHash(leaves[2],leaves[3]) at level 1.
    const sibling0 = leaves[1]!;
    const sibling1 = pairHash(leaves[2]!, leaves[3]!);
    expect(verifyMerkleProof(leaves[0]!, [sibling0, sibling1], root, 0)).toBe(
      true,
    );
    expect(verifyMerkleProof(sha256Hex("tampered"), [sibling0, sibling1], root, 0)).toBe(
      false,
    );
  });
});

describe("keccakHex", () => {
  it("matches the OpenZeppelin keccak fixture for the empty string", () => {
    // keccak256("") == c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470
    expect(keccakHex("")).toBe(
      "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470",
    );
  });
});

describe("keccakPairSorted", () => {
  it("is order-insensitive (sorted-pair regime)", () => {
    const a = keccakHex("a");
    const b = keccakHex("b");
    expect(keccakPairSorted(a, b)).toBe(keccakPairSorted(b, a));
  });

  it("normalises 0x-prefixed and unprefixed inputs identically", () => {
    const a = keccakHex("a");
    const b = keccakHex("b");
    const stripped = a.replace(/^0x/, "");
    expect(keccakPairSorted(stripped, b)).toBe(keccakPairSorted(a, b));
  });
});

describe("verifyMerkleProofEvm (sorted-pair keccak)", () => {
  it("accepts a hand-built 3-leaf proof matching the Solidity contract", () => {
    // Mirrors contracts/test/LandRegistryAnchor.t.sol::test_VerifyProof_ThreeLeaves.
    // Here we build the keccak leaves directly (no SHA-256 bridge) to match the
    // Solidity-side test verbatim.
    const leafA = keccakHex("alpha");
    const leafB = keccakHex("beta");
    const leafC = keccakHex("gamma");
    const ab = keccakPairSorted(leafA, leafB);
    const cc = keccakPairSorted(leafC, leafC);
    const root = keccakPairSorted(ab, cc);
    expect(verifyMerkleProofEvm(leafA, [leafB, cc], root)).toBe(true);
    expect(verifyMerkleProofEvm(keccakHex("tampered"), [leafB, cc], root)).toBe(false);
  });

  it("treats hex case-insensitively when comparing leaf to root", () => {
    const leaf = keccakHex("x");
    expect(verifyMerkleProofEvm(leaf, [], leaf.toUpperCase())).toBe(true);
  });
});
