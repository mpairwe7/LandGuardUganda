"""Tiered rate-limiting decorators wrapping slowapi."""

from __future__ import annotations

from typing import Callable

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

_settings = get_settings()
limiter = Limiter(key_func=get_remote_address, storage_uri=_settings.redis_url)


def limit_anon(func: Callable) -> Callable:
    return limiter.limit(_settings.rate_limit_anon)(func)


def limit_auth(func: Callable) -> Callable:
    return limiter.limit(_settings.rate_limit_auth)(func)


def limit_admin(func: Callable) -> Callable:
    return limiter.limit(_settings.rate_limit_admin)(func)


def limit_public_verify(func: Callable) -> Callable:
    return limiter.limit(_settings.rate_limit_public_verify)(func)
