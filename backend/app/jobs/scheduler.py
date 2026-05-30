"""Replica-safe periodic scheduler for governance batch jobs.

Runs inside the API lifespan but takes a Redis leader-lock (``cache_setnx``)
each tick, so with N API replicas at most one runs the jobs per tick. This
replaces the "wire into cron" TODO that was never actually wired — the 24h
escalation (:func:`app.jobs.escalation.escalate_pending`) and the periodic
parity audit (:func:`app.jobs.parity.run_parity_audit`) now actually run.

With no Redis, ``cache_setnx`` falls back to an in-process guard, which is
correct for single-replica dev/pilot deployments.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.jobs.escalation import escalate_pending
from app.jobs.parity import run_parity_audit
from app.util.cache import cache_setnx

logger = logging.getLogger(__name__)

TICK_SECONDS = 300.0
LEADER_LOCK_KEY = "scheduler:leader"
PARITY_INTERVAL_SECONDS = 30 * 86400.0  # ~monthly

_RUNNING = False
_last_parity = 0.0


async def _is_leader() -> bool:
    # Hold leadership for slightly less than a tick so it frees before the next.
    return await cache_setnx(LEADER_LOCK_KEY, "1", ttl_seconds=int(TICK_SECONDS) - 30)


async def _run_tick() -> None:
    global _last_parity
    # Escalation is cheap + idempotent — safe to attempt every tick.
    try:
        await asyncio.to_thread(escalate_pending)
    except Exception:
        logger.exception("scheduler_escalation_error")
    now = time.time()
    if now - _last_parity >= PARITY_INTERVAL_SECONDS:
        _last_parity = now
        try:
            await asyncio.to_thread(run_parity_audit)
        except Exception:
            logger.exception("scheduler_parity_error")


async def scheduler_loop_forever() -> None:
    """Tick every ``TICK_SECONDS``; only the leader replica runs the jobs."""
    global _RUNNING
    if _RUNNING:
        return
    _RUNNING = True
    while _RUNNING:
        try:
            if await _is_leader():
                await _run_tick()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("scheduler_tick_error")
        try:
            await asyncio.sleep(TICK_SECONDS)
        except asyncio.CancelledError:
            break


def stop_scheduler() -> None:
    global _RUNNING
    _RUNNING = False
