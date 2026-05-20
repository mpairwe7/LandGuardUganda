"""FastAPI dependencies that resolve :class:`AuthContext` per request."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import get_settings

from .jwt_auth import JWTAuthError, JWTVerifier
from .models import AuthContext, AuthUser, Role

logger = logging.getLogger(__name__)

_VERIFIER: JWTVerifier | None = None


def _get_verifier() -> JWTVerifier:
    global _VERIFIER
    if _VERIFIER is None:
        _VERIFIER = JWTVerifier()
    return _VERIFIER


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


async def optional_user(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_demo_role: Annotated[str | None, Header(alias="X-Demo-Role")] = None,
    x_demo_district: Annotated[int | None, Header(alias="X-Demo-District")] = None,
) -> AuthContext | None:
    """Resolve an AuthContext if a valid token is present; else None."""
    settings = get_settings()
    token = _extract_bearer(authorization)

    # DEMO_MODE escape hatch: on-stage role switching via header.
    # Strictly gated to non-production.
    if (
        settings.demo_mode
        and settings.app_env != "production"
        and x_demo_role
        and not token
    ):
        role = Role.parse(x_demo_role) or Role.CITIZEN
        user = AuthUser(
            user_id=f"demo-{role.value.lower()}",
            role=role,
            district_id=x_demo_district,
            full_name=f"Demo {role.value.title()}",
            email=None,
        )
        return AuthContext(
            user=user,
            raw_token="",
            claims={"demo": True, "role": role.value, "district_id": x_demo_district},
        )

    if not token:
        return None
    try:
        claims = await _get_verifier().verify(token)
    except JWTAuthError as exc:
        logger.info("auth_token_invalid", extra={"reason": str(exc)})
        return None
    role = Role.parse(claims.get("role")) or Role.CITIZEN
    user = AuthUser(
        user_id=str(claims.get("sub") or claims.get("user_id") or ""),
        role=role,
        district_id=claims.get("district_id"),
        full_name=str(claims.get("full_name") or claims.get("name") or "Anonymous"),
        email=claims.get("email"),
    )
    ctx = AuthContext(user=user, raw_token=token, claims=claims)
    # Stash in request state for downstream middleware (audit_actor).
    request.state.auth = ctx
    return ctx


async def require_user(
    ctx: Annotated[AuthContext | None, Depends(optional_user)],
) -> AuthContext:
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


def require_role(*allowed: Role):
    """FastAPI dependency factory that gates a route to roles in ``allowed``."""

    async def _dep(ctx: Annotated[AuthContext, Depends(require_user)]) -> AuthContext:
        if not ctx.has_role(*allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(r.value for r in allowed)}",
            )
        return ctx

    return _dep


# Alias used by FastAPI route signatures.
current_user = require_user
