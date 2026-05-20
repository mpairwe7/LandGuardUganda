"""Circuit breaker behaviour."""

from __future__ import annotations

import asyncio

import pytest

from app.resilience import CircuitBreaker, CircuitOpenError


@pytest.mark.asyncio
async def test_breaker_opens_after_threshold_failures():
    breaker = CircuitBreaker(name="test", failure_threshold=3, reset_timeout=0.05)

    async def boom():
        raise RuntimeError("nope")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.call(boom)
    with pytest.raises(CircuitOpenError):
        await breaker.call(boom)


@pytest.mark.asyncio
async def test_breaker_recovers_via_half_open():
    breaker = CircuitBreaker(name="test", failure_threshold=2, reset_timeout=0.05)

    async def boom():
        raise RuntimeError("nope")

    async def ok():
        return "ok"

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(boom)
    await asyncio.sleep(0.06)
    result = await breaker.call(ok)
    assert result == "ok"


def test_force_open_and_close():
    b = CircuitBreaker()
    b.force_open()
    assert b.state.value == "open"
    b.force_close()
    assert b.state.value == "closed"
