"""Production-safety guard (G6).

A production deploy must hard-fail at startup if it would anchor with the
committed Anvil dev signing key, or with single-signer custody.
"""

from __future__ import annotations

import pytest

from app.config import _ANVIL_DEV_PRIVATE_KEY, Settings

# A configuration that is safe for production on every dimension; individual
# tests flip exactly one field to prove that field is checked.
_SAFE = {
    "app_env": "production",
    "auth_mode": "oidc",
    "demo_mode": False,
    "blockchain_provider": "sepolia",
    "jwt_hs256_secret": "x" * 40,
    "pii_encryption_key": "dGVzdGtleS0zMi1ieXRlcy0wMTIzNDU2Nzg5MDEyMzQ1Ng==",
    "registrar_private_key": "0x" + "1" * 64,
    "multisig_enabled": True,
}


def test_safe_production_config_passes():
    Settings(**_SAFE).assert_prod_safety()  # must not raise


def test_default_registrar_key_rejected_in_prod():
    s = Settings(**{**_SAFE, "registrar_private_key": _ANVIL_DEV_PRIVATE_KEY})
    with pytest.raises(RuntimeError) as ei:
        s.assert_prod_safety()
    assert "REGISTRAR_PRIVATE_KEY" in str(ei.value)


def test_single_signer_rejected_in_prod():
    s = Settings(**{**_SAFE, "multisig_enabled": False})
    with pytest.raises(RuntimeError) as ei:
        s.assert_prod_safety()
    assert "MULTISIG_ENABLED" in str(ei.value)
