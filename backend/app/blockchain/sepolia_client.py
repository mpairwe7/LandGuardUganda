"""Sepolia testnet blockchain client.

Identical to :class:`AnvilBlockchainClient` except for:
- EIP-1559 fee strategy (maxFeePerGas + maxPriorityFeePerGas)
- production-shaped logging
- the private key MUST come from a secrets manager (env in dev only)

# MIGRATION TO MAINNET: change ``chain_id`` via env and replace the
# in-process key with a remote signer (e.g. AWS KMS, GCP Cloud KMS).
# Never commit a mainnet private key to env files.
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
from app.blockchain.anvil_client import _to_bytes32
from app.blockchain.models import AnchorReceipt
from app.config import get_settings

logger = logging.getLogger(__name__)

_ABI_PATH = Path(__file__).resolve().parent / "abi.json"


class SepoliaBlockchainClient:
    name = "sepolia"

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.sepolia_rpc_url:
            raise RuntimeError("SEPOLIA_RPC_URL must be set when BLOCKCHAIN_PROVIDER=sepolia")
        self.chain_id = self._settings.sepolia_chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(self._settings.sepolia_rpc_url))
        self._account = Account.from_key(self._settings.registrar_private_key)
        with _ABI_PATH.open() as f:
            self._abi = json.load(f)
        self._address = self._read_address()
        self._tx_lock = asyncio.Lock()

    def _read_address(self) -> str | None:
        path = self._settings.contract_address_file
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        addr = data.get("sepolia") or data.get("address")
        return str(addr or "").lower() or None

    @property
    def address(self) -> str:
        if not self._address:
            self._address = self._read_address()
        if not self._address:
            raise RuntimeError(
                "LandRegistryAnchor Sepolia address unknown — deploy first and pin in contract_address.json"
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
        async with self._tx_lock:
            nonce = await self._w3.eth.get_transaction_count(
                self._account.address, "pending"
            )
            latest = await self._w3.eth.get_block("latest")
            base = latest.get("baseFeePerGas") or 1_000_000_000
            priority = 2_000_000_000  # 2 gwei tip
            tx = await contract.functions.commitBatch(
                int(district_id), b32_batch, b32_root
            ).build_transaction(
                {
                    "from": self._account.address,
                    "nonce": nonce,
                    "gas": 250_000,
                    "maxFeePerGas": base * 2 + priority,
                    "maxPriorityFeePerGas": priority,
                    "chainId": self.chain_id,
                    "type": 2,
                }
            )
            signed = self._account.sign_transaction(tx)
            tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        submitted_at = time.time()
        try:
            receipt = await asyncio.wait_for(
                self._w3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=2.0),
                timeout=180.0,
            )
        except asyncio.TimeoutError:
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
