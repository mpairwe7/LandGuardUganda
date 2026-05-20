"""Cross-language Merkle fixtures.

Proves the off-chain Python implementation produces proofs that the on-chain
Solidity ``verifyProof`` accepts. Used in CI as a regression test against the
Merkle inconsistency we fixed in May 2026 — see ADR-0001.

The actual on-chain check happens in ``tests/integration/test_anchor_to_chain.py``
where Anvil is spun up; here we use the pure-Python mirror
``verify_merkle_proof_evm`` which by construction implements the exact same
algorithm as the contract.
"""

from __future__ import annotations

from app.audit.merkle import (
    compute_merkle_root_evm,
    keccak_hex,
    keccak_pair_sorted,
    merkle_proof_evm,
    sha256_hex,
    verify_merkle_proof_evm,
)

# ---------------------------------------------------------------------------
# Published test vector — included in DEMO handout for offline cross-checking.
# Anyone with a keccak library can independently recompute these values.
# ---------------------------------------------------------------------------

PUBLIC_FIXTURE = {
    "events": [
        {"title_no": "UG-MIT-T00001/2026", "owner": "Sarah Nakato"},
        {"title_no": "UG-MIT-T00002/2026", "owner": "Joseph Okello"},
        {"title_no": "UG-MIT-T00003/2026", "owner": "Aisha Namatovu"},
        {"title_no": "UG-MIT-T00004/2026", "owner": "Esther Auma"},
        {"title_no": "UG-MIT-T00005/2026", "owner": "Patrick Mukasa"},
    ],
}


def _canonical_leaves() -> list[str]:
    """Deterministic SHA-256 leaves from the published fixture."""
    import json

    return [
        sha256_hex(json.dumps(e, sort_keys=True))
        for e in PUBLIC_FIXTURE["events"]
    ]


def test_keccak_hex_deterministic():
    # keccak("abc") — published Ethereum test vector
    assert (
        keccak_hex("abc")
        == "0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
    )


def test_keccak_pair_sorted_independent_of_input_order():
    a = "0x" + ("a" * 64)
    b = "0x" + ("b" * 64)
    assert keccak_pair_sorted(a, b) == keccak_pair_sorted(b, a)


def test_single_leaf_root_is_keccak_of_leaf():
    leaves = ["a" * 64]
    root = compute_merkle_root_evm(leaves)
    # Single-leaf tree: root == keccak(sha256_hex_leaf)
    assert root == keccak_hex("a" * 64)


def test_published_fixture_proofs_all_verify():
    leaves = _canonical_leaves()
    root = compute_merkle_root_evm(leaves)
    for i in range(len(leaves)):
        proof = merkle_proof_evm(leaves, i)
        assert proof["root"] == root
        assert verify_merkle_proof_evm(
            leaf_hex=proof["leaf"],
            siblings=proof["siblings"],
            root=root,
        ), f"leaf {i} failed verification"


def test_tampered_leaf_does_not_verify():
    leaves = _canonical_leaves()
    proof = merkle_proof_evm(leaves, 2)
    tampered_leaf = "0x" + ("f" * 64)
    assert not verify_merkle_proof_evm(
        leaf_hex=tampered_leaf,
        siblings=proof["siblings"],
        root=proof["root"],
    )


def test_tampered_sibling_does_not_verify():
    leaves = _canonical_leaves()
    proof = merkle_proof_evm(leaves, 2)
    tampered_siblings = list(proof["siblings"])
    tampered_siblings[0] = "0x" + ("f" * 64)
    assert not verify_merkle_proof_evm(
        leaf_hex=proof["leaf"],
        siblings=tampered_siblings,
        root=proof["root"],
    )


def test_proof_for_odd_length_tree():
    # Three leaves → duplicate-last at level 0 → 2 sibling proof.
    leaves = ["1" * 64, "2" * 64, "3" * 64]
    proof = merkle_proof_evm(leaves, 2)
    assert len(proof["siblings"]) == 2
    assert verify_merkle_proof_evm(
        leaf_hex=proof["leaf"],
        siblings=proof["siblings"],
        root=proof["root"],
    )
