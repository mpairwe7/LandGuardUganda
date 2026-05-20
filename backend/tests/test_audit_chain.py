"""Hash-chain integrity + Merkle root cross-check."""

from __future__ import annotations

import pytest

from app.audit import get_ledger, reset_ledger
from app.audit.merkle import compute_merkle_root, merkle_proof, verify_merkle_proof
from app.audit.verifier import verify_chain


@pytest.fixture(autouse=True)
def _fresh_ledger():
    reset_ledger()
    yield
    reset_ledger()


def test_append_and_verify_chain():
    ledger = get_ledger()
    events = [
        ledger.append(
            event_type="TITLE_ISSUED",
            payload={"title_no": f"T-{i}", "n": i},
            tenant_id="3",
            user_id="alice",
        )
        for i in range(10)
    ]
    assert [e.seq for e in events] == list(range(1, 11))
    report = verify_chain("3")
    assert report.verified, report.reason
    assert report.total_events == 10


def test_merkle_proof_roundtrip():
    leaves = [f"leaf-{i:04d}" for i in range(7)]
    root = compute_merkle_root(leaves)
    proof = merkle_proof(leaves, index=4)
    assert verify_merkle_proof(leaf=leaves[4], proof=proof, root=root, index=4)
    # Wrong leaf must not verify
    assert not verify_merkle_proof(
        leaf="tampered", proof=proof, root=root, index=4
    )


def test_tenant_isolation():
    ledger = get_ledger()
    ledger.append("TITLE_ISSUED", {"x": 1}, tenant_id="3", user_id="alice")
    ledger.append("TITLE_ISSUED", {"x": 2}, tenant_id="3", user_id="alice")
    ledger.append("TITLE_ISSUED", {"y": 1}, tenant_id="4", user_id="bob")
    assert ledger.count("3") == 2
    assert ledger.count("4") == 1
    assert verify_chain("3").verified
    assert verify_chain("4").verified
