"""Auth domain models — small, frozen, framework-free."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Role(str, Enum):
    CITIZEN = "CITIZEN"
    SURVEYOR = "SURVEYOR"
    LAND_OFFICER = "LAND_OFFICER"
    REGISTRAR = "REGISTRAR"
    AUDITOR = "AUDITOR"
    PUBLIC_VERIFIER = "PUBLIC_VERIFIER"
    ADMIN = "ADMIN"

    @classmethod
    def parse(cls, raw: str | None) -> Role | None:
        if not raw:
            return None
        try:
            return cls(raw.upper())
        except ValueError:
            return None


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    role: Role
    district_id: int | None
    full_name: str
    email: str | None = None


@dataclass(frozen=True)
class AuthContext:
    """Per-request authentication context.

    Threaded through every router via the :func:`require_user` dep.
    The audit layer reads ``district_id`` + ``user_id`` to label every
    event with its actor.
    """

    user: AuthUser
    raw_token: str
    claims: dict[str, Any]

    @property
    def tenant_id(self) -> str:
        return str(self.user.district_id) if self.user.district_id is not None else "_global"

    @property
    def user_id(self) -> str:
        return self.user.user_id

    @property
    def role(self) -> Role:
        return self.user.role

    def has_role(self, *allowed: Role) -> bool:
        if self.user.role is Role.ADMIN:
            return True
        return self.user.role in allowed
