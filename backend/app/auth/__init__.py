"""Zero-trust JWT auth for LandGuard Uganda.

Pattern from the FinalYearProject sibling: every request carries a
JWT whose claims include the actor's ``district_id`` (multi-tenant
boundary), ``role`` (RBAC), and ``user_id`` (for audit). Two verification
backends:

- **dev**: HS256 with a shared secret (``JWT_HS256_SECRET``)
- **oidc**: RS256 with JWKS fetched from ``OIDC_JWKS_URL`` — drop-in
  for NIRA's planned ID broker or a Uganda-government IDP

A ``DEMO_MODE=true`` build also accepts X-Demo-Role header for
on-stage role-switching during the showcase. Disabled in production.
"""

from __future__ import annotations

from .dependencies import (
    AuthContext,
    current_user,
    optional_user,
    require_role,
    require_user,
)
from .jwt_auth import (
    JWTAuthError,
    JWTVerifier,
    make_dev_token,
)
from .models import AuthUser, Role

__all__ = [
    "AuthContext",
    "AuthUser",
    "JWTAuthError",
    "JWTVerifier",
    "Role",
    "current_user",
    "make_dev_token",
    "optional_user",
    "require_role",
    "require_user",
]
