"""Multi-sig anchor client.

Wraps an underlying single-signer client (``AnvilBlockchainClient`` or
``SepoliaBlockchainClient``) and routes ``commit_batch`` through
``MultiSigRegistrar.proposeAndConfirm`` instead. The proposer key signs
first; additional confirmations come from co-signers either via the
``CoSignerDaemon`` (demo) or external HSM-protected signers (production).

# CUSTODY MODEL (see docs/CUSTODY.md)
# Five named signers, three required:
#   1. MoLHUD Commissioner Land Registration (HSM)
#   2. NITA-U Security Lead (HSM)
#   3. District Land Board chair (mobile signer + biometric)
#   4. LandGuard project signer (the backend key in this file)
#   5. Independent auditor (offline signer; can veto by withholding signature)
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

_MULTISIG_ABI_PATH = Path(__file__).resolve().parent / "multisig_abi.json"


def _load_abi() -> list[dict[str, Any]]:
    with _MULTISIG_ABI_PATH.open() as f:
        return json.load(f)


def _read_address_for_multisig(file_path: str) -> str | None:
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    addr = data.get("multisig_address")
    return str(addr or "").lower() or None


class MultiSigBlockchainClient:
    """Proxy that routes every commit through the k-of-n multi-sig."""

    name = "multisig"

    def __init__(self, *, single_signer_client: Any) -> None:
        self._settings = get_settings()
        self._inner = single_signer_client  # used for verify_proof + health
        self.chain_id = single_signer_client.chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(self._settings.rpc_url))
        self._account = Account.from_key(self._settings.registrar_private_key)
        self._abi = _load_abi()
        self._address = _read_address_for_multisig(self._settings.contract_address_file)
        self._tx_lock = asyncio.Lock()

    @property
    def address(self) -> str:
        if not self._address:
            self._address = _read_address_for_multisig(self._settings.contract_address_file)
        if not self._address:
            raise RuntimeError(
                "MultiSigRegistrar address unknown — run scripts/deploy_contract.py"
            )
        return self._address

    def _contract(self) -> Any:
        return self._w3.eth.contract(
            address=self._w3.to_checksum_address(self.address),
            abi=self._abi,
        )

    async def commit_batch(
        self,
        *,
        batch_id: str,
        district_id: int,
        merkle_root_hex: str,
    ) -> AnchorReceipt:
        """First-signer submission. Co-signers complete the threshold separately.

        Returns immediately with status ``SUBMITTED`` once the first
        confirmation is mined. The actual on-chain ``commitBatch`` fires when
        the third confirmation lands; the anchor service polls
        ``verify_proof`` afterwards to confirm.
        """
        contract = self._contract()
        b32_batch = _to_bytes32(sha256_hex(batch_id))
        b32_root = _to_bytes32(merkle_root_hex)
        async with self._tx_lock:
            nonce = await self._w3.eth.get_transaction_count(
                self._account.address, "pending"
            )
            tx = await contract.functions.proposeAndConfirm(
                int(district_id), b32_batch, b32_root
            ).build_transaction(
                {
                    "from": self._account.address,
                    "nonce": nonce,
                    "gas": 300_000,
                    "gasPrice": await self._w3.eth.gas_price,
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
        # First confirmation is in. The proposal will execute once co-signers
        # bring confirmations to threshold. Poll briefly to give the demo
        # co-signer daemon a chance to land.
        executed = await self._wait_for_execution(b32_batch, max_wait=10.0)
        status = "CONFIRMED" if executed else "SUBMITTED"
        return AnchorReceipt(
            batch_id=batch_id,
            district_id=district_id,
            merkle_root=merkle_root_hex,
            tx_hash=tx_hash.hex(),
            block_number=int(receipt.blockNumber) if receipt else None,
            chain_id=self.chain_id,
            submitted_at=submitted_at,
            confirmed_at=time.time() if executed else None,
            status=status,
        )

    async def _wait_for_execution(self, batch_id: HexBytes, max_wait: float) -> bool:
        contract = self._contract()
        # We don't have a direct "isExecuted" view; we re-derive proposalId
        # by re-hashing on the client side. For the demo we instead poll the
        # underlying anchor: if the batchId is present there, the multisig
        # has fired.
        deadline = time.time() + max_wait
        inner_addr = getattr(self._inner, "address", None)
        if not inner_addr:
            return False
        from pathlib import Path as _P

        abi_path = _P(__file__).resolve().parent / "abi.json"
        with abi_path.open() as f:
            anchor_abi = json.load(f)
        anchor = self._w3.eth.contract(
            address=self._w3.to_checksum_address(inner_addr),
            abi=anchor_abi,
        )
        while time.time() < deadline:
            try:
                stored = await anchor.functions.anchors(batch_id).call()
                if stored and stored[2] != 0:  # timestamp > 0 → executed
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False

    async def verify_proof(
        self,
        *,
        batch_id: str,
        leaf_hex: str,
        proof_hex: list[str],
    ) -> bool:
        return await self._inner.verify_proof(
            batch_id=batch_id, leaf_hex=leaf_hex, proof_hex=proof_hex
        )

    async def health(self) -> dict[str, Any]:
        inner_health = await self._inner.health()
        return {
            "provider": "multisig",
            "inner": inner_health,
            "multisig_address": self._address,
            "threshold": "3-of-5",
        }
