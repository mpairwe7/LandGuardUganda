"""BlockchainClient protocol + factory.

Production-realistic abstraction so the rest of the backend never
imports web3 directly. Three implementations:
- ``MockBlockchainClient`` (deterministic, used in tests)
- ``AnvilBlockchainClient`` (default for dev/demo)
- ``SepoliaBlockchainClient`` (one env-var migration)

# MIGRATION: To target a different EVM chain (Polygon zkEVM, a
# regional EAC permissioned chain, or a Ugandan government-operated
# chain), copy ``sepolia_client.py``, point its RPC URL at the new
# chain, and update ``ChainSelector`` below to instantiate it.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.blockchain.models import AnchorReceipt
from app.config import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class BlockchainClient(Protocol):
    """The minimum surface that the anchor service needs."""

    chain_id: int
    name: str

    async def commit_batch(
        self,
        *,
        batch_id: str,
        district_id: int,
        merkle_root_hex: str,
    ) -> AnchorReceipt:
        ...

    async def verify_proof(
        self,
        *,
        batch_id: str,
        leaf_hex: str,
        proof_hex: list[str],
    ) -> bool:
        ...

    async def health(self) -> dict[str, object]:
        ...


_CLIENT: BlockchainClient | None = None


def get_blockchain_client() -> BlockchainClient:
    """Lazy singleton — the active client per ``BLOCKCHAIN_PROVIDER``.

    When ``MULTISIG_ENABLED=true``, the chosen single-signer client is
    wrapped in :class:`MultiSigBlockchainClient` so every ``commit_batch``
    routes through ``MultiSigRegistrar.proposeAndConfirm`` and requires
    three-of-five named co-signers to land on chain. Single-signer mode
    is retained for non-production environments (testing, dev, the
    25 June showcase if MULTISIG_ENABLED=false).
    """
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    settings = get_settings()
    provider = settings.blockchain_provider
    if provider == "mock":
        from .mock_client import MockBlockchainClient

        _CLIENT = MockBlockchainClient()
    elif provider == "anvil":
        from .anvil_client import AnvilBlockchainClient

        _CLIENT = AnvilBlockchainClient()
    elif provider == "sepolia":
        from .sepolia_client import SepoliaBlockchainClient

        _CLIENT = SepoliaBlockchainClient()
    else:
        raise ValueError(f"unknown BLOCKCHAIN_PROVIDER: {provider}")

    if settings.multisig_enabled and provider != "mock":
        from .multisig_client import MultiSigBlockchainClient

        _CLIENT = MultiSigBlockchainClient(single_signer_client=_CLIENT)
        logger.info(
            "blockchain_client_selected",
            extra={"provider": provider, "custody": "multisig-3-of-5"},
        )
    else:
        logger.info(
            "blockchain_client_selected",
            extra={"provider": provider, "custody": "single-signer"},
        )
    return _CLIENT


def reset_blockchain_client() -> None:
    """Test-only: drop the singleton."""
    global _CLIENT
    _CLIENT = None
