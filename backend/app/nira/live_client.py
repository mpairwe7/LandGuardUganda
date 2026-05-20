"""Placeholder live NIRA client.

# MIGRATION TO LIVE NIRA:
# 1. Add NIRA_BASE_URL + NIRA_API_KEY to env (or KMS in prod).
# 2. Replace the three stub methods below with real httpx calls.
# 3. Set ``NIRA_PROVIDER=live`` and restart.
#
# All callers go through :func:`app.nira.client.get_nira_client` so
# nothing else in the system needs to change.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.nira.client import (
    NIRABiometricMatch,
    NIRADemographics,
    NIRAVerifyResult,
)

logger = logging.getLogger(__name__)


class LiveNIRAClient:
    name = "live"

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.nira_base_url:
            raise RuntimeError("NIRA_BASE_URL is required when NIRA_PROVIDER=live")
        self._client = httpx.AsyncClient(
            base_url=self._settings.nira_base_url,
            headers={"Authorization": f"Bearer {self._settings.nira_api_key}"},
            timeout=httpx.Timeout(connect=2.0, read=4.0, write=2.0, pool=2.0),
        )

    async def verify_nin(self, nin: str) -> NIRAVerifyResult:
        # TODO(LIVE-NIRA): replace this stub with the real endpoint shape
        # once NIRA publishes its 2026 API spec to MoICT&NG.
        resp = await self._client.post("/verify", json={"nin": nin})
        resp.raise_for_status()
        body = resp.json()
        demo = body.get("demographics") or None
        return NIRAVerifyResult(
            nin_valid=bool(body.get("nin_valid")),
            matched=bool(body.get("matched")),
            demographics=NIRADemographics(**demo) if demo else None,
            reason=body.get("reason"),
            source="NIRA_LIVE",
        )

    async def fetch_demographics(self, nin: str) -> NIRADemographics | None:
        result = await self.verify_nin(nin)
        return result.demographics

    async def biometric_match(self, nin: str, template: bytes) -> NIRABiometricMatch:
        files = {"template": ("tpl.bin", template, "application/octet-stream")}
        resp = await self._client.post("/biometric", data={"nin": nin}, files=files)
        resp.raise_for_status()
        body = resp.json()
        return NIRABiometricMatch(
            matched=bool(body["matched"]),
            confidence=float(body["confidence"]),
            template_hash=str(body["template_hash"]),
        )

    async def health(self) -> dict[str, Any]:
        try:
            resp = await self._client.get("/health")
            return {"provider": "live", "ok": resp.status_code < 500, "status": resp.status_code}
        except Exception as exc:
            return {"provider": "live", "ok": False, "error": str(exc)}
