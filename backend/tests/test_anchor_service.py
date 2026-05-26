"""End-to-end anchor flow against the MockBlockchainClient."""

from __future__ import annotations

import time

import pytest

from app.audit import get_ledger
from app.blockchain.anchor_service import build_proof_for_event, flush_district
from app.blockchain.client import get_blockchain_client
from app.database import get_connection


@pytest.fixture(autouse=True)
def _reset_state():
    # conftest._clean_tables already wipes business tables + resets singletons.
    # We just ensure the Mityana district exists for FK references.
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO districts (id, name, region, created_at) VALUES (3,'Mityana','Central',?)",
            (time.time(),),
        )
        conn.commit()
    yield


@pytest.mark.asyncio
async def test_flush_anchors_and_proof_verifies():
    ledger = get_ledger()
    for i in range(5):
        ledger.append(
            event_type="TITLE_ISSUED",
            payload={"title_no": f"UG-MIT-T{i:05d}/2026", "ts": time.time()},
            tenant_id="3",
            user_id="alice",
        )
    receipt = await flush_district(district_id=3, force=True)
    assert receipt["status"] == "CONFIRMED"
    proof = build_proof_for_event(district_id=3, leaf_seq=3)
    assert proof is not None
    # The proof is in EVM keccak form, byte-identical to what
    # LandRegistryAnchor.verifyProof would accept.
    assert proof.leaf.startswith("0x")
    assert all(s.startswith("0x") for s in proof.siblings)
    client = get_blockchain_client()
    ok = await client.verify_proof(
        batch_id=proof.batch_id,
        leaf_hex=proof.leaf,
        proof_hex=proof.siblings,
    )
    assert ok


@pytest.mark.asyncio
async def test_proof_root_matches_anchor_root():
    """The proof's root field MUST equal the on-chain anchored root."""
    ledger = get_ledger()
    for i in range(7):
        ledger.append("TITLE_ISSUED", {"i": i}, tenant_id="3", user_id="alice")
    receipt = await flush_district(district_id=3, force=True)
    assert receipt["status"] == "CONFIRMED"
    # Pick a middle leaf and an edge leaf; both must produce proofs whose
    # root equals the anchored merkle_root.
    for seq in (1, 4, 7):
        proof = build_proof_for_event(district_id=3, leaf_seq=seq)
        assert proof is not None
        assert proof.root == receipt["merkle_root"]


@pytest.mark.asyncio
async def test_flush_empty_is_safe():
    receipt = await flush_district(district_id=3, force=True)
    assert receipt["status"] == "EMPTY"
