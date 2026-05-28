#!/usr/bin/env python3
"""LandGuard offline title verifier — single-file, audit-grade, no network.

This is the "anyone, anywhere" verifier behind Public Claim 1. A citizen, a
journalist, or a foreign auditor can clone this one file (and ``pip install
eth-utils``) and verify a LandGuard title proof against a published Merkle
root, with no chain access, no LandGuard backend, and no JavaScript runtime.

The keccak sorted-pair logic is intentionally inlined — mirroring
``LandRegistryAnchor.verifyProof`` and ``app.audit.merkle.verify_merkle_proof_evm``
byte-for-byte. CI guards the parity via ``contracts/test/merkle-parity.json``.

USAGE

    # Verify one inclusion proof bundle.
    python scripts/verify_offline.py --bundle proof.json

    # Override the trusted root (e.g. one you fetched from Etherscan).
    python scripts/verify_offline.py --bundle proof.json --root 0xabc...

    # Run the cross-language parity fixture end-to-end.
    python scripts/verify_offline.py --parity contracts/test/merkle-parity.json

Bundle format (``--bundle``):

    {
      "leaf":    "0x...",          // keccak(sha256_hex_leaf), 32 bytes
      "siblings":["0x...", ...],   // each 32 bytes
      "root":    "0x..."           // optional if --root is passed
    }

Exit codes: 0 = every proof verified, 1 = at least one failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from eth_utils import keccak as _keccak
except ImportError as exc:  # pragma: no cover — user-actionable error path
    sys.stderr.write(
        "verify_offline: missing dependency 'eth-utils'.\n"
        "  Install with:  pip install eth-utils\n"
        f"  Original error: {exc}\n"
    )
    raise SystemExit(2) from exc


# ---------------------------------------------------------------------------
# Inline keccak sorted-pair verifier (mirror of backend/app/audit/merkle.py)
# ---------------------------------------------------------------------------


def _hex_to_bytes32(value: str) -> bytes:
    s = value.lower().removeprefix("0x")
    if len(s) < 64:
        s = s.zfill(64)
    elif len(s) > 64:
        s = s[-64:]
    return bytes.fromhex(s)


def _keccak_pair_sorted(left_hex: str, right_hex: str) -> str:
    a = _hex_to_bytes32(left_hex)
    b = _hex_to_bytes32(right_hex)
    lo, hi = (a, b) if a <= b else (b, a)
    return "0x" + _keccak(lo + hi).hex()


def verify(leaf_hex: str, siblings: list[str], root_hex: str) -> bool:
    """Return True iff the sorted-pair keccak proof reduces to ``root_hex``."""
    h = leaf_hex
    for sibling in siblings:
        h = _keccak_pair_sorted(h, sibling)
    return h.lower() == root_hex.lower()


# ---------------------------------------------------------------------------
# Bundle + parity-fixture loaders
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"verify_offline: file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"verify_offline: invalid JSON in {path}: {exc}") from exc


def _verify_bundle(bundle_path: Path, override_root: str | None) -> bool:
    bundle = _load_json(bundle_path)
    leaf = bundle.get("leaf")
    siblings = bundle.get("siblings")
    root = override_root or bundle.get("root")
    if not isinstance(leaf, str) or not isinstance(siblings, list) or not isinstance(root, str):
        raise SystemExit(
            "verify_offline: bundle must contain string 'leaf', list 'siblings', "
            "and string 'root' (or pass --root)."
        )
    ok = verify(leaf, siblings, root)
    print(f"{'PASS' if ok else 'FAIL'}  leaf={leaf[:18]}…  root={root[:18]}…")
    return ok


def _verify_parity(parity_path: Path) -> bool:
    fixture = _load_json(parity_path)
    if fixture.get("schema_version") != 1:
        raise SystemExit(
            f"verify_offline: unsupported parity schema_version "
            f"{fixture.get('schema_version')!r}; regenerate via "
            "backend/scripts/emit_merkle_vectors.py"
        )
    total = 0
    failed = 0
    for case in fixture.get("cases", []):
        name = case.get("name", "<unnamed>")
        for proof in case.get("evm", {}).get("proofs", []):
            total += 1
            ok = verify(proof["leaf"], proof["siblings"], proof["root"])
            if not ok:
                failed += 1
                print(f"FAIL  {name} idx={proof.get('index')}")
    summary = f"verified {total - failed}/{total} proofs across {len(fixture.get('cases', []))} cases"
    print(("PASS  " if failed == 0 else "FAIL  ") + summary)
    return failed == 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline LandGuard Merkle proof verifier.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  verify a single bundle:\n"
            "    python scripts/verify_offline.py --bundle proof.json\n"
            "  run the canonical parity fixture:\n"
            "    python scripts/verify_offline.py --parity contracts/test/merkle-parity.json\n"
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bundle", type=Path, help="single-proof JSON file")
    group.add_argument("--parity", type=Path, help="parity fixture JSON file")
    parser.add_argument("--root", help="override trusted root (--bundle mode only)")
    args = parser.parse_args(argv)

    if args.parity is not None:
        if args.root is not None:
            parser.error("--root is only valid with --bundle")
        ok = _verify_parity(args.parity)
    else:
        ok = _verify_bundle(args.bundle, args.root)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
