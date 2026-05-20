"""Shared resilience primitives — circuit breaker, retry, bulkheads.

2026 production standard: each external dependency (NIRA, blockchain
RPC, third-party APIs) gets its own breaker so one slow dependency
cannot exhaust the request pool via thundering-herd.

Reused pattern from the FinalYearProject sibling; adapted to expose
an async-friendly `call()` plus a sync variant.
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the breaker is OPEN."""


class CircuitBreaker:
    """Thread-safe circuit breaker with exponential backoff.

    - CLOSED: requests flow; consecutive failures counted.
    - OPEN: requests rejected immediately; waits ``reset_timeout``
      (doubles on each HALF_OPEN→OPEN trip, capped at ``max_timeout``).
    - HALF_OPEN: one probe allowed; success → CLOSED, failure → OPEN.
    """

    def __init__(
        self,
        name: str = "breaker",
        failure_threshold: int = 3,
        reset_timeout: float = 10.0,
        max_timeout: float = 300.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self._initial_reset_timeout = reset_timeout
        self._current_reset_timeout = reset_timeout
        self.max_timeout = max_timeout

        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_half_open_locked()
            return self._state

    def _maybe_half_open_locked(self) -> None:
        if self._state is CircuitState.OPEN and (
            time.monotonic() - self._opened_at >= self._current_reset_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            logger.info(
                "circuit_breaker_half_open",
                extra={"breaker": self.name, "reset_timeout": self._current_reset_timeout},
            )

    def _record_success_locked(self) -> None:
        if self._state in {CircuitState.HALF_OPEN, CircuitState.OPEN}:
            logger.info("circuit_breaker_closed", extra={"breaker": self.name})
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._current_reset_timeout = self._initial_reset_timeout

    def _record_failure_locked(self) -> None:
        self._failures += 1
        if self._state is CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._current_reset_timeout = min(
                self._current_reset_timeout * 2, self.max_timeout
            )
            logger.warning(
                "circuit_breaker_reopened",
                extra={"breaker": self.name, "reset_timeout": self._current_reset_timeout},
            )
            return
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "circuit_breaker_opened",
                extra={
                    "breaker": self.name,
                    "failures": self._failures,
                    "reset_timeout": self._current_reset_timeout,
                },
            )

    def _preflight(self) -> None:
        with self._lock:
            self._maybe_half_open_locked()
            if self._state is CircuitState.OPEN:
                raise CircuitOpenError(f"breaker {self.name!r} is OPEN")

    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        self._preflight()
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._record_failure_locked()
            raise
        with self._lock:
            self._record_success_locked()
        return result

    def call_sync(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        self._preflight()
        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._record_failure_locked()
            raise
        with self._lock:
            self._record_success_locked()
        return result

    def force_open(self) -> None:
        """Force the breaker open — used by the demo control panel."""
        with self._lock:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._failures = self.failure_threshold
            logger.warning("circuit_breaker_forced_open", extra={"breaker": self.name})

    def force_close(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._current_reset_timeout = self._initial_reset_timeout
            logger.info("circuit_breaker_forced_closed", extra={"breaker": self.name})


async def retry_with_backoff(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
    jitter: float = 0.1,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """Generic exponential backoff retry helper.

    Use this when you want retries *inside* a breaker call so transient
    failures don't immediately count against the failure threshold.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except retry_on as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay += random.uniform(0, jitter)
            logger.info(
                "retrying_after_failure",
                extra={"attempt": attempt, "delay": delay, "error": str(exc)},
            )
            await asyncio.sleep(delay)
    assert last_exc is not None  # for mypy
    raise last_exc
