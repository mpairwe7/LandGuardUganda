"""Deterministic mock NIRA client.

Drives the showcase demo. A handful of seeded NINs return realistic
results; everything else is generated deterministically from
``sha256(nin)[:8]``.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.nira.client import (
    NIRABiometricMatch,
    NIRADemographics,
    NIRAVerifyResult,
)
from app.util.ids import validate_nin

# Pre-seeded demo identities. The Mityana hero, the fraudster, etc.
_SEEDED: dict[str, NIRADemographics | None] = {
    "CM82010110A4P0": NIRADemographics(
        full_name="Sarah Nakato",
        dob="1982-01-01",
        gender="F",
        district_of_birth="Mityana",
    ),
    "CM85030212B7Q1": NIRADemographics(
        full_name="Joseph Okello",
        dob="1985-03-02",
        gender="M",
        district_of_birth="Gulu",
    ),
    "CM91070514C9R2": NIRADemographics(
        full_name="Aisha Namatovu",
        dob="1991-07-05",
        gender="F",
        district_of_birth="Wakiso",
    ),
    "CM88110316D2S3": NIRADemographics(
        full_name="Esther Auma",
        dob="1988-11-03",
        gender="F",
        district_of_birth="Kampala",
    ),
    "CM82010110A4P9": None,  # The fraudster forgery — NIRA returns "no match".
}


def _hash_prefix(nin: str) -> str:
    return hashlib.sha256(nin.encode("utf-8")).hexdigest()[:8]


class MockNIRAClient:
    name = "mock"

    async def verify_nin(self, nin: str) -> NIRAVerifyResult:
        if not validate_nin(nin):
            return NIRAVerifyResult(
                nin_valid=False,
                matched=False,
                demographics=None,
                reason="format_invalid",
            )
        if nin in _SEEDED:
            demo = _SEEDED[nin]
            if demo is None:
                return NIRAVerifyResult(
                    nin_valid=True,
                    matched=False,
                    demographics=None,
                    reason="nin_not_in_register",
                )
            return NIRAVerifyResult(
                nin_valid=True,
                matched=True,
                demographics=demo,
                reason=None,
            )
        # Deterministic synthesis for non-seeded NINs.
        digest = _hash_prefix(nin)
        if digest.startswith("0") or digest.startswith("1"):
            # Roughly 12% of unknown NINs are "not found" — gives the
            # demo a realistic failure surface without hand-curation.
            return NIRAVerifyResult(
                nin_valid=True,
                matched=False,
                demographics=None,
                reason="nin_not_in_register",
            )
        gender = "F" if int(digest[0], 16) % 2 == 0 else "M"
        year = 1970 + (int(digest[1:3], 16) % 40)
        synthetic = NIRADemographics(
            full_name=f"Demo Citizen {digest.upper()}",
            dob=f"{year}-06-15",
            gender=gender,
            district_of_birth="Wakiso",
        )
        return NIRAVerifyResult(
            nin_valid=True,
            matched=True,
            demographics=synthetic,
            reason=None,
        )

    async def fetch_demographics(self, nin: str) -> NIRADemographics | None:
        result = await self.verify_nin(nin)
        return result.demographics

    async def biometric_match(self, nin: str, template: bytes) -> NIRABiometricMatch:
        if not template:
            return NIRABiometricMatch(matched=False, confidence=0.0, template_hash="")
        # The fraudster path: biometric vastly mismatches because the
        # template was tampered with.
        nin_digest = _hash_prefix(nin)
        tpl_digest = hashlib.sha256(template).hexdigest()[:8]
        match = nin_digest[:4] == tpl_digest[:4]
        confidence = 0.92 if match else 0.31
        return NIRABiometricMatch(
            matched=match,
            confidence=confidence,
            template_hash=hashlib.sha256(template).hexdigest(),
        )

    async def health(self) -> dict[str, Any]:
        return {"provider": "mock", "ok": True}
