"""Deterministic in-memory blockchain client — for unit tests + demos.

No network I/O. Tx hashes derived from inputs so the same anchor
always returns the same receipt — useful for fixtures.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

from app.audit.merkle import verify_merkle_proof_evm
from app.blockchain.models import AnchorReceipt


class MockBlockchainClient:
    name = "mock"
    chain_id = 0

    def __init__(self) -> None:
        self._anchors: dict[str, dict[str, Any]] = {}
        self._block = 1_000_000
        self._lock = asyncio.Lock()

    async def commit_batch(
        self,
        *,
        batch_id: str,
        district_id: int,
        merkle_root_hex: str,
    ) -> AnchorReceipt:
        async with self._lock:
            tx_hash = "0x" + hashlib.sha256(
                f"{batch_id}|{district_id}|{merkle_root_hex}".encode()
            ).hexdigest()
            self._block += 1
            block_no = self._block
            now = time.time()
            self._anchors[batch_id] = {
                "merkle_root": merkle_root_hex,
                "district_id": district_id,
                "tx_hash": tx_hash,
                "block_number": block_no,
                "timestamp": now,
            }
            return AnchorReceipt(
                batch_id=batch_id,
                district_id=district_id,
                merkle_root=merkle_root_hex,
                tx_hash=tx_hash,
                block_number=block_no,
                chain_id=self.chain_id,
                submitted_at=now,
                confirmed_at=now,
                status="CONFIRMED",
            )

    async def verify_proof(
        self,
        *,
        batch_id: str,
        leaf_hex: str,
        proof_hex: list[str],
    ) -> bool:
        """Mirror of the on-chain ``verifyProof`` — pure-Python keccak."""
        anchor = self._anchors.get(batch_id)
        if not anchor:
            return False
        return verify_merkle_proof_evm(
            leaf_hex=leaf_hex,
            siblings=proof_hex,
            root=str(anchor["merkle_root"]),
        )

    async def health(self) -> dict[str, Any]:
        return {"provider": "mock", "ok": True, "block": self._block}
