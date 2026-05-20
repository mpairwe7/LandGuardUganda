#!/usr/bin/env python
"""Deploy LandRegistryAnchor (and optionally MultiSigRegistrar) to the active chain.

Reads ``BLOCKCHAIN_PROVIDER`` to pick anvil or sepolia. If ``MULTISIG_ENABLED``
is true, also deploys ``MultiSigRegistrar`` with five named signers and rotates
the ``REGISTRAR_ROLE`` to the multi-sig — so no single key can anchor.

Writes both addresses (and ABIs) to ``data_store/contract_address.json``.

For the prototype's Anvil profile we use a fixed set of five well-known
test accounts as signers; in production each signer is a hardware-protected
key held by:
  1. MoLHUD Commissioner Land Registration
  2. NITA-U Security Lead
  3. District Land Board chair
  4. LandGuard project signer (this backend)
  5. Independent auditor / civil-society observer
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402


def _load_artifact(name: str) -> tuple[list[dict], str]:
    """Read Foundry-compiled artifact for ``name`` (LandRegistryAnchor or MultiSigRegistrar)."""
    candidates = [
        ROOT.parent / "contracts" / "out" / f"{name}.sol" / f"{name}.json",
    ]
    for c in candidates:
        if c.exists():
            with c.open() as f:
                artifact = json.load(f)
            return artifact["abi"], artifact["bytecode"]["object"]
    raise RuntimeError(
        f"Compiled artifact for {name} not found. Run `cd contracts && forge build` first.\n"
        f"Looked in: {candidates}"
    )


# Anvil deterministic accounts 1-5 (account 0 is the backend signer).
ANVIL_COSIGNERS = [
    ("0x70997970C51812dc3A010C7d01b50e0d17dc79C8", "MoLHUD Commissioner"),
    ("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC", "NITA-U Security Lead"),
    ("0x90F79bf6EB2c4f870365E785982E1f101E93b906", "District Land Board"),
    ("0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65", "Independent Auditor"),
]
# Anvil account 0 (the backend signer) is also part of the 3-of-5 set.
ANVIL_BACKEND_SIGNER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


async def main() -> None:
    from eth_account import Account
    from web3 import AsyncWeb3
    from web3 import AsyncHTTPProvider

    settings = get_settings()
    rpc_url = settings.rpc_url
    chain_id = settings.chain_id

    anchor_abi, anchor_bytecode = _load_artifact("LandRegistryAnchor")
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
    deployer = Account.from_key(settings.registrar_private_key)

    # --- Deploy anchor ---
    nonce = await w3.eth.get_transaction_count(deployer.address)
    anchor_contract = w3.eth.contract(abi=anchor_abi, bytecode=anchor_bytecode)
    tx = await anchor_contract.constructor(deployer.address).build_transaction(
        {
            "from": deployer.address,
            "nonce": nonce,
            "gas": 3_000_000,
            "gasPrice": await w3.eth.gas_price,
            "chainId": chain_id,
        }
    )
    signed = deployer.sign_transaction(tx)
    tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=0.5)
    anchor_address = receipt.contractAddress
    print(f"LandRegistryAnchor deployed at: {anchor_address} (block {receipt.blockNumber})")

    multisig_address: str | None = None

    if settings.multisig_enabled:
        # --- Deploy multisig ---
        ms_abi, ms_bytecode = _load_artifact("MultiSigRegistrar")
        signers = [ANVIL_BACKEND_SIGNER] + [addr for addr, _ in ANVIL_COSIGNERS]
        nonce = await w3.eth.get_transaction_count(deployer.address)
        ms = w3.eth.contract(abi=ms_abi, bytecode=ms_bytecode)
        tx = await ms.constructor(signers, 3, anchor_address).build_transaction(
            {
                "from": deployer.address,
                "nonce": nonce,
                "gas": 3_500_000,
                "gasPrice": await w3.eth.gas_price,
                "chainId": chain_id,
            }
        )
        signed = deployer.sign_transaction(tx)
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=0.5)
        multisig_address = receipt.contractAddress
        print(f"MultiSigRegistrar deployed at: {multisig_address}")

        # --- Rotate REGISTRAR_ROLE: grant to multisig, revoke from deployer ---
        anchor = w3.eth.contract(
            address=w3.to_checksum_address(anchor_address), abi=anchor_abi
        )
        registrar_role = await anchor.functions.REGISTRAR_ROLE().call()
        for fn_name, target, label in [
            ("grantRole", multisig_address, "grant multisig"),
            ("revokeRole", deployer.address, "revoke deployer"),
        ]:
            nonce = await w3.eth.get_transaction_count(deployer.address)
            method = getattr(anchor.functions, fn_name)
            tx = await method(registrar_role, target).build_transaction(
                {
                    "from": deployer.address,
                    "nonce": nonce,
                    "gas": 200_000,
                    "gasPrice": await w3.eth.gas_price,
                    "chainId": chain_id,
                }
            )
            signed = deployer.sign_transaction(tx)
            tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
            await w3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=0.5)
            print(f"  ✓ {label} ({fn_name})")
        print("REGISTRAR_ROLE rotated: only the 3-of-5 multisig can anchor now.")

    out_path = Path(settings.contract_address_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "address": anchor_address.lower(),
        "chain_id": chain_id,
        "block": int(receipt.blockNumber),
        "rpc_url": rpc_url,
        "multisig_enabled": settings.multisig_enabled,
        "multisig_address": multisig_address.lower() if multisig_address else None,
        "custody_signers": (
            [{"address": ANVIL_BACKEND_SIGNER, "role": "LandGuard backend"}]
            + [{"address": a, "role": r} for a, r in ANVIL_COSIGNERS]
            if multisig_address
            else None
        ),
    }
    if settings.blockchain_provider == "sepolia":
        payload["sepolia"] = anchor_address.lower()
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
