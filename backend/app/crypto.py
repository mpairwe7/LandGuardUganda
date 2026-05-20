"""AES-GCM helpers for at-rest PII encryption (e.g. raw NIN).

In production the key is fetched from KMS/HSM (``app.config`` validates
key strength at startup). In development it's a static base64 string.
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


@lru_cache(maxsize=1)
def _get_key() -> bytes:
    settings = get_settings()
    key = base64.b64decode(settings.pii_encryption_key)
    if len(key) < 32:
        raise RuntimeError("PII_ENCRYPTION_KEY too short after b64 decode")
    return key[:32]  # AES-256


def encrypt(plaintext: str, *, associated_data: bytes | None = None) -> bytes:
    """Encrypt UTF-8 plaintext; returns nonce || ciphertext as raw bytes."""
    aes = AESGCM(_get_key())
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), associated_data)
    return nonce + ct


def decrypt(blob: bytes, *, associated_data: bytes | None = None) -> str:
    """Decrypt the nonce || ciphertext blob produced by :func:`encrypt`."""
    if len(blob) < 13:
        raise ValueError("ciphertext too short")
    nonce, ct = blob[:12], blob[12:]
    aes = AESGCM(_get_key())
    return aes.decrypt(nonce, ct, associated_data).decode("utf-8")
