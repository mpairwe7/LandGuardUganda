"""Emit canonical Merkle test vectors used across Python, TypeScript, Solidity.

Single source of truth for the cross-language parity claim in
``backend/app/audit/merkle.py``, ``frontend/src/lib/merkle.ts``, and
``contracts/src/LandRegistryAnchor.sol::verifyProof``.

Run from the repo root:

    uv run --project backend python backend/scripts/emit_merkle_vectors.py \
        --out contracts/test/merkle-parity.json

Re-runs are idempotent for fixed inputs. Regenerate any time the underlying
hashing rule changes (which would also be a breaking change to public Claim 2,
so this script is the one place to catch the drift).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Allow ``backend/`` on PYTHONPATH whether invoked from the repo root or from
# inside ``backend/``.
THIS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = THIS_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.audit.merkle import (  # noqa: E402 — sys.path bootstrap above
    compute_merkle_root,
    compute_merkle_root_evm,
    keccak_hex,
    merkle_proof,
    merkle_proof_evm,
    sha256_hex,
    sha256_leaves_to_keccak,
    verify_merkle_proof,
    verify_merkle_proof_evm,
)

SCHEMA_VERSION = 1


def _sha256_block(inputs: list[str]) -> dict[str, Any]:
    leaves = [sha256_hex(s) for s in inputs]
    if not leaves:
        return {"leaves": [], "root": "", "proofs": []}
    root = compute_merkle_root(leaves)
    proofs = []
    for idx, leaf in enumerate(leaves):
        siblings = merkle_proof(leaves, idx)
        assert verify_merkle_proof(leaf, siblings, root, idx), (
            f"SHA-256 self-check failed for index {idx}"
        )
        proofs.append({"index": idx, "leaf": leaf, "siblings": siblings, "root": root})
    return {"leaves": leaves, "root": root, "proofs": proofs}


def _evm_block(inputs: list[str]) -> dict[str, Any]:
    sha_leaves = [sha256_hex(s) for s in inputs]
    if not sha_leaves:
        return {"leaves": [], "root": "", "proofs": []}
    keccak_leaves = sha256_leaves_to_keccak(sha_leaves)
    root = compute_merkle_root_evm(sha_leaves)
    proofs = []
    for idx in range(len(sha_leaves)):
        proof = merkle_proof_evm(sha_leaves, idx)
        assert verify_merkle_proof_evm(proof["leaf"], proof["siblings"], proof["root"]), (
            f"EVM self-check failed for index {idx}"
        )
        proofs.append({"index": idx, **proof})
    return {"leaves": keccak_leaves, "root": root, "proofs": proofs}


def _case(name: str, inputs: list[str], comment: str | None = None) -> dict[str, Any]:
    case: dict[str, Any] = {
        "name": name,
        "inputs": inputs,
        "sha256": _sha256_block(inputs),
        "evm": _evm_block(inputs),
        "skip_solidity": len(inputs) == 0,
    }
    if comment:
        case["_comment"] = comment
    return case


def _hand_derived_two_leaf_case() -> dict[str, Any]:
    """A case with an explicit step-by-step derivation in ``_comment``.

    Lets a panellist re-derive the keccak root on paper with only a keccak
    primitive. If this case disagrees with the runtime, every other case is
    suspect.
    """
    inputs = ["alpha", "beta"]
    sha_a = sha256_hex("alpha")
    sha_b = sha256_hex("beta")
    k_a = keccak_hex(sha_a)
    k_b = keccak_hex(sha_b)
    # Sort the two keccak leaves to derive the root.
    lo, hi = sorted([k_a, k_b])
    case = _case("two-leaves-hand-derived", inputs)
    case["_comment"] = (
        "Hand-derivation:\n"
        f"  sha256('alpha')                = {sha_a}\n"
        f"  sha256('beta')                 = {sha_b}\n"
        f"  keccak(UTF8 of sha256-hex 'alpha') = {k_a}\n"
        f"  keccak(UTF8 of sha256-hex 'beta')  = {k_b}\n"
        f"  sorted pair concat (lo,hi)     = ({lo}, {hi})\n"
        f"  root = keccak(lo || hi)        = {case['evm']['root']}\n"
        "Any panellist with a keccak primitive can reproduce this in 30 seconds."
    )
    return case


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    cases.append(
        _case(
            "empty",
            [],
            "Empty input yields the empty string root in both regimes — the "
            "Solidity verifyProof never sees this state (commitBatch rejects "
            "zero roots); included for Python/TS exhaustiveness.",
        )
    )
    cases.append(
        _case(
            "single-leaf",
            ["only"],
            "Single leaf: root == leaf. Verifier accepts empty proof.",
        )
    )
    cases.append(_hand_derived_two_leaf_case())
    cases.append(
        _case(
            "three-leaves-odd",
            ["alpha", "beta", "gamma"],
            "Odd leaf count exercises duplicate-last semantics at level 0. "
            "Mirrors contracts/test/LandRegistryAnchor.t.sol::test_VerifyProof_ThreeLeaves.",
        )
    )
    cases.append(_case("four-leaves", ["a", "b", "c", "d"]))
    cases.append(
        _case(
            "eight-leaves",
            ["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p7"],
            "Balanced binary tree, no duplicate-last anywhere.",
        )
    )
    cases.append(
        _case(
            "sixteen-leaves",
            [f"event-{i:02d}" for i in range(16)],
            "Real-world batch shape (~16 events per anchor under normal load).",
        )
    )
    cases.append(
        _case(
            "five-leaves-odd",
            ["q0", "q1", "q2", "q3", "q4"],
            "Odd count at multiple levels — duplicate-last fires twice.",
        )
    )
    cases.append(
        _case(
            "permuted-order",
            ["b", "c", "a", "d"],
            "Input ordering matters: this produces a different root than "
            "'a','b','c','d'. The verifier MUST NOT accept a proof generated "
            "against the sorted-input tree if the leaves are out of order.",
        )
    )
    cases.append(
        _case(
            "real-uganda-batch",
            [
                "TITLE_ISSUED:UG-MIT-T00007/2026",
                "TRANSFER_INITIATED:UG-MIT-T00012/2026",
                "FRAUD_HUMAN_AFFIRMED:UG-MIT-T00003/2026",
                "ANCHOR_COMMITTED:0x1234...",
                "USSD_VERIFY:UG-MIT-T00007/2026",
            ],
            "Five realistic audit-event leaves drawn from Mityana pilot scope. "
            "Hashes the event-type:id form, not raw PII (per project invariant #2).",
        )
    )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="contracts/test/merkle-parity.json",
        help="Output path relative to repo root (default: contracts/test/merkle-parity.json)",
    )
    args = parser.parse_args()

    cases = build_cases()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "regimes": ["sha256_index_ordered", "keccak_sorted_pair"],
        "generated_by": "backend/scripts/emit_merkle_vectors.py",
        "_note": (
            "Single source of truth for cross-language Merkle parity. Loaded by "
            "frontend/src/__tests__/merkle.parity.test.ts, "
            "contracts/test/MerkleParity.t.sol, and "
            "scripts/verify_offline.py. Regenerate via the command in this file's "
            "module docstring."
        ),
        "cases": cases,
    }

    # Resolve output path relative to repo root (the parent of backend/).
    repo_root = BACKEND_DIR.parent
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = repo_root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    rel = os.path.relpath(out_path, repo_root)
    print(f"wrote {len(cases)} cases to {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
