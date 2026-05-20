"""NIRAClient protocol + factory + result dataclasses."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NIRADemographics:
    full_name: str
    dob: str  # YYYY-MM-DD
    gender: str  # "M" | "F" | "X"
    district_of_birth: str | None
    nationality: str = "UG"

    def to_dict(self) -> dict[str, Any]:
        return {
            "full_name": self.full_name,
            "dob": self.dob,
            "gender": self.gender,
            "district_of_birth": self.district_of_birth,
            "nationality": self.nationality,
        }


@dataclass(frozen=True)
class NIRAVerifyResult:
    nin_valid: bool
    matched: bool
    demographics: NIRADemographics | None
    reason: str | None
    source: str = "MOCK"

    def to_dict(self) -> dict[str, Any]:
        return {
            "nin_valid": self.nin_valid,
            "matched": self.matched,
            "demographics": self.demographics.to_dict() if self.demographics else None,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass(frozen=True)
class NIRABiometricMatch:
    matched: bool
    confidence: float  # 0.0–1.0
    template_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "confidence": self.confidence,
            "template_hash": self.template_hash,
        }


@runtime_checkable
class NIRAClient(Protocol):
    name: str

    async def verify_nin(self, nin: str) -> NIRAVerifyResult:
        ...

    async def fetch_demographics(self, nin: str) -> NIRADemographics | None:
        ...

    async def biometric_match(self, nin: str, template: bytes) -> NIRABiometricMatch:
        ...

    async def health(self) -> dict[str, Any]:
        ...


_CLIENT: NIRAClient | None = None


def get_nira_client() -> NIRAClient:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    settings = get_settings()
    if settings.nira_provider == "mock":
        from .mock_client import MockNIRAClient

        _CLIENT = MockNIRAClient()
    else:
        from .live_client import LiveNIRAClient

        _CLIENT = LiveNIRAClient()
    logger.info("nira_client_selected", extra={"provider": _CLIENT.name})
    return _CLIENT


def reset_nira_client() -> None:
    global _CLIENT
    _CLIENT = None
