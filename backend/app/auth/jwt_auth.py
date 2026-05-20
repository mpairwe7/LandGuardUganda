"""JWT verification (HS256 dev / RS256 OIDC) for LandGuard.

Backed by PyJWT (+ cryptography for RSA). We intentionally do *not* use
python-jose because it pulls in the ``ecdsa`` package, which has an
unpatched CVE (CVE-2024-23342, Minerva timing-attack). We do not sign
with ECDSA — JWT auth is HS256 (dev) or RS256 (prod OIDC) — but
eliminating the transitive dep is cleaner than documenting an
inapplicable advisory.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import jwt
from jwt import InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from app.config import get_settings

logger = logging.getLogger(__name__)


class JWTAuthError(Exception):
    """Raised when token verification fails."""


class JWTVerifier:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_fetched_at: float = 0.0

    async def _get_jwks(self) -> dict[str, Any]:
        url = self._settings.oidc_jwks_url
        if not url:
            raise JWTAuthError("OIDC_JWKS_URL not configured for AUTH_MODE=oidc")
        # 5-minute JWKS cache. Production should also handle rotation events.
        if self._jwks_cache and time.time() - self._jwks_fetched_at < 300:
            return self._jwks_cache
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        self._jwks_cache = resp.json()
        self._jwks_fetched_at = time.time()
        return self._jwks_cache

    @staticmethod
    def _key_for(jwks: dict[str, Any], kid: str | None) -> Any:
        """Return a PyJWT-compatible RSA key for the token's kid.

        If the token carries no kid and there is exactly one key in the
        JWKS, use it (some OPs publish a single key without kids).
        """
        keys = jwks.get("keys", [])
        if not keys:
            raise JWTAuthError("JWKS contains no keys")
        if kid is None:
            if len(keys) == 1:
                return RSAAlgorithm.from_jwk(keys[0])
            raise JWTAuthError("token missing kid and JWKS has multiple keys")
        for jwk in keys:
            if jwk.get("kid") == kid:
                return RSAAlgorithm.from_jwk(jwk)
        raise JWTAuthError(f"no matching JWKS key for kid={kid}")

    async def verify(self, token: str) -> dict[str, Any]:
        settings = self._settings
        try:
            if settings.auth_mode == "oidc":
                header = jwt.get_unverified_header(token)
                jwks = await self._get_jwks()
                key = self._key_for(jwks, header.get("kid"))
                claims = jwt.decode(
                    token,
                    key,
                    algorithms=["RS256"],
                    audience=settings.jwt_audience,
                    issuer=settings.jwt_issuer,
                )
            else:
                claims = jwt.decode(
                    token,
                    settings.jwt_hs256_secret,
                    algorithms=["HS256"],
                    audience=settings.jwt_audience,
                    issuer=settings.jwt_issuer,
                )
        except InvalidTokenError as exc:
            raise JWTAuthError(f"invalid token: {exc}") from exc
        if not isinstance(claims, dict):
            raise JWTAuthError("token payload is not an object")
        return claims


def make_dev_token(
    *,
    user_id: str,
    role: str,
    district_id: int | None,
    full_name: str,
    email: str | None = None,
    ttl_seconds: int = 3600,
) -> str:
    """Issue an HS256 token for local dev / demo only.

    NEVER call this from production code paths. The CLI script
    ``scripts/issue_dev_tokens.py`` uses it to mint one token per
    role for the showcase demo.
    """
    settings = get_settings()
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": user_id,
        "iat": now,
        "exp": now + ttl_seconds,
        "role": role,
        "district_id": district_id,
        "full_name": full_name,
        "email": email,
    }
    return jwt.encode(payload, settings.jwt_hs256_secret, algorithm="HS256")
