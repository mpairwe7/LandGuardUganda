"""Local Anvil (Foundry) blockchain client — the prototype default.

Talks to a local Anvil node at ``ANVIL_RPC_URL``. The same code works
against any EVM-compatible chain — only ``sepolia_client.py`` differs
in its env-var defaults and gas/priority strategy.

# MIGRATION: To target a different chain, copy this file and change
# the RPC URL, chain ID, and (optionally) gas pricing strategy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from eth_account import Account
from hexbytes import HexBytes
from web3 import AsyncWeb3
from web3 import AsyncHTTPProvider

from app.audit.merkle import sha256_hex
from app.blockchain.models import AnchorReceipt
from app.config import get_settings

logger = logging.getLogger(__name__)

_ABI_PATH = Path(__file__).resolve().parent / "abi.json"


def _load_abi() -> list[dict[str, Any]]:
    with _ABI_PATH.open() as f:
        return json.load(f)


def _read_contract_address(file_path: str) -> str | None:
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("address") or "").lower() or None
    except Exception:
        logger.exception("read_contract_address_failed", extra={"file": file_path})
        return None


def _to_bytes32(hex_or_str: str) -> HexBytes:
    s = hex_or_str.lower().removeprefix("0x")
    if len(s) < 64:
        s = s.zfill(64)
    elif len(s) > 64:
        s = s[:64]
    return HexBytes("0x" + s)


# Note: leaf-bridging (SHA-256 hex → keccak(hex)) now happens inside
# ``app.audit.merkle.compute_merkle_root_evm`` and ``merkle_proof_evm``,
# so by the time a leaf reaches ``verify_proof`` here it is already keccak
# bytes32 hex. We just hex-decode and pass through.


class AnvilBlockchainClient:
    name = "anvil"

    def __init__(self) -> None:
        self._settings = get_settings()
        self.chain_id = self._settings.chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(self._settings.rpc_url))
        self._account = Account.from_key(self._settings.registrar_private_key)
        self._abi = _load_abi()
        self._address: str | None = _read_contract_address(
            self._settings.contract_address_file
        )
        self._tx_lock = asyncio.Lock()

    @property
    def address(self) -> str:
        if not self._address:
            # Re-read in case deploy ran after process startup (Docker init order).
            self._address = _read_contract_address(self._settings.contract_address_file)
        if not self._address:
            raise RuntimeError(
                "LandRegistryAnchor address unknown — run scripts/deploy_contract.py first"
            )
        return self._address

    def _contract(self) -> Any:
        return self._w3.eth.contract(address=self._w3.to_checksum_address(self.address), abi=self._abi)

    async def commit_batch(
        self,
        *,
        batch_id: str,
        district_id: int,
        merkle_root_hex: str,
    ) -> AnchorReceipt:
        contract = self._contract()
        b32_batch = _to_bytes32(sha256_hex(batch_id))
        b32_root = _to_bytes32(merkle_root_hex)
        # nonce must be serialised — concurrent anchors would otherwise
        # race the same nonce and one would fail.
        async with self._tx_lock:
            nonce = await self._w3.eth.get_transaction_count(self._account.address, "pending")
            gas_price = await self._w3.eth.gas_price
            tx = await contract.functions.commitBatch(
                int(district_id), b32_batch, b32_root
            ).build_transaction(
                {
                    "from": self._account.address,
                    "nonce": nonce,
                    "gas": 250_000,
                    "gasPrice": gas_price,
                    "chainId": self.chain_id,
                }
            )
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        submitted_at = time.time()
        try:
            receipt = await asyncio.wait_for(
                self._w3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=0.5),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "anchor_tx_pending",
                extra={"batch_id": batch_id, "tx": tx_hash.hex()},
            )
            return AnchorReceipt(
                batch_id=batch_id,
                district_id=district_id,
                merkle_root=merkle_root_hex,
                tx_hash=tx_hash.hex(),
                block_number=None,
                chain_id=self.chain_id,
                submitted_at=submitted_at,
                confirmed_at=None,
                status="SUBMITTED",
            )
        status = "CONFIRMED" if receipt.status == 1 else "FAILED"
        return AnchorReceipt(
            batch_id=batch_id,
            district_id=district_id,
            merkle_root=merkle_root_hex,
            tx_hash=tx_hash.hex(),
            block_number=int(receipt.blockNumber),
            chain_id=self.chain_id,
            submitted_at=submitted_at,
            confirmed_at=time.time(),
            status=status,
        )

    async def verify_proof(
        self,
        *,
        batch_id: str,
        leaf_hex: str,
        proof_hex: list[str],
    ) -> bool:
        """Verify against the on-chain ``LandRegistryAnchor.verifyProof``.

        ``leaf_hex`` and every entry in ``proof_hex`` must already be keccak
        bytes32 hex (0x-prefixed). The off-chain proof builder produces them
        in this form via ``merkle_proof_evm``.
        """
        contract = self._contract()
        b32_batch = _to_bytes32(sha256_hex(batch_id))
        leaf_b32 = _to_bytes32(leaf_hex)
        proof_b32 = [_to_bytes32(p) for p in proof_hex]
        return bool(
            await contract.functions.verifyProof(b32_batch, leaf_b32, proof_b32).call()
        )

    async def health(self) -> dict[str, Any]:
        try:
            block = await self._w3.eth.block_number
            return {
                "provider": self.name,
                "ok": True,
                "chain_id": self.chain_id,
                "block": block,
                "contract": self._address,
            }
        except Exception as exc:
            return {"provider": self.name, "ok": False, "error": str(exc)}
