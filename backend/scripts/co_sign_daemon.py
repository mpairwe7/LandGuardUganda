#!/usr/bin/env python
"""Demo co-signer daemon.

Watches the MultiSigRegistrar for new ``ProposalCreated`` events and submits
co-signature confirmations from the configured demo keys (Anvil accounts 1
and 2 by default). Brings the threshold from 1 → 3 in ~2 seconds so the
showcase audience sees a multi-sig anchor land in a single live demo step.

In production this is replaced by independent signing services held by
MoLHUD, NITA-U, the District Land Board, and the auditor — each one running
their own variant of this daemon against HSM-protected keys with human
approval workflows in front.

Usage:
    uv run python scripts/co_sign_daemon.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

logger = logging.getLogger("co_sign_daemon")

# Anvil-default co-signers (accounts 1, 2 — MoLHUD + NITA-U personas).
DEFAULT_COSIGNERS = [
    "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
]


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from eth_account import Account
    from web3 import AsyncWeb3
    from web3 import AsyncHTTPProvider

    settings = get_settings()
    if not settings.multisig_enabled:
        logger.warning("MULTISIG_ENABLED=false — daemon has nothing to do")
        return

    cosigner_keys = (
        [k.strip() for k in settings.cosigner_private_keys.split(",") if k.strip()]
        or DEFAULT_COSIGNERS
    )

    w3 = AsyncWeb3(AsyncHTTPProvider(settings.rpc_url))
    addresses_path = Path(settings.contract_address_file)
    if not addresses_path.exists():
        logger.error("contract_address.json missing — run deploy_contract.py first")
        return
    data = json.loads(addresses_path.read_text())
    multisig_address = data.get("multisig_address")
    if not multisig_address:
        logger.error("multisig_address not set — re-deploy with MULTISIG_ENABLED=true")
        return
    abi_path = Path(__file__).resolve().parent.parent / "app" / "blockchain" / "multisig_abi.json"
    abi = json.loads(abi_path.read_text())
    contract = w3.eth.contract(
        address=w3.to_checksum_address(multisig_address), abi=abi
    )
    accounts = [Account.from_key(k) for k in cosigner_keys]

    logger.info(
        "co_sign_daemon_ready",
        extra={
            "multisig": multisig_address,
            "cosigners": [a.address for a in accounts],
        },
    )

    # Subscribe to ProposalCreated via polling (Anvil websockets are flaky).
    last_block = await w3.eth.block_number
    while True:
        try:
            current = await w3.eth.block_number
            if current > last_block:
                events = await contract.events.ProposalCreated().get_logs(
                    from_block=last_block + 1, to_block=current
                )
                for evt in events:
                    args = evt["args"]
                    await _confirm(w3, contract, accounts, args)
                last_block = current
        except Exception:
            logger.exception("polling_error")
        await asyncio.sleep(0.5)


async def _confirm(w3, contract, accounts, args) -> None:
    district_id = args["districtId"]
    batch_id = args["batchId"]
    merkle_root = args["merkleRoot"]
    proposal_id = args["proposalId"]
    logger.info(
        "proposal_seen",
        extra={
            "proposal_id": proposal_id.hex(),
            "district_id": district_id,
            "merkle_root": merkle_root.hex(),
        },
    )
    for acct in accounts:
        try:
            already = await contract.functions.proposals(proposal_id).call()
            # already[4] is `executed`; if True we can stop.
            if already[4]:
                logger.info("proposal_already_executed", extra={"proposal_id": proposal_id.hex()})
                return
        except Exception:
            pass
        try:
            nonce = await w3.eth.get_transaction_count(acct.address, "pending")
            tx = await contract.functions.proposeAndConfirm(
                int(district_id), batch_id, merkle_root
            ).build_transaction(
                {
                    "from": acct.address,
                    "nonce": nonce,
                    "gas": 250_000,
                    "gasPrice": await w3.eth.gas_price,
                    "chainId": await w3.eth.chain_id,
                }
            )
            signed = acct.sign_transaction(tx)
            tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
            await w3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=0.5)
            logger.info(
                "confirmation_submitted",
                extra={"signer": acct.address, "tx": tx_hash.hex()},
            )
        except Exception:
            logger.exception("confirmation_failed", extra={"signer": acct.address})


if __name__ == "__main__":
    asyncio.run(main())
