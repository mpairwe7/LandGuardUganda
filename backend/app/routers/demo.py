"""Demo Control Panel endpoints — gated by DEMO_MODE.

These exist to orchestrate the 25 June 2026 showcase: kill the RPC,
restore it, force an anchor flush, reset state. They are HARD-DISABLED
when ``APP_ENV=production`` so no operator can accidentally pause the
real chain integration from a console.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from app.blockchain.anchor_service import flush_district, get_anchor_breaker
from app.config import get_settings
from app.database import get_connection
from app.fraud.worker import enqueue_score
from app.nira.cache import get_nira_breaker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


def _ensure_enabled() -> None:
    settings = get_settings()
    # Single-source-of-truth gate: production deploys never serve the
    # demo router (Settings.assert_prod_safety() ensures this is the
    # only thing we need to check). We deliberately do NOT also require
    # DEMO_MODE=true — that double-flag pattern caused a deployment
    # footgun where the showcase /demo page silently 404'd.
    if settings.app_env == "production":
        raise HTTPException(status_code=403, detail="demo endpoints disabled in production")


@router.post("/rpc-kill")
async def rpc_kill() -> dict[str, object]:
    _ensure_enabled()
    get_anchor_breaker().force_open()
    logger.warning("demo_rpc_killed")
    return {"breaker_state": get_anchor_breaker().state.value}


@router.post("/rpc-restore")
async def rpc_restore() -> dict[str, object]:
    _ensure_enabled()
    get_anchor_breaker().force_close()
    logger.info("demo_rpc_restored")
    return {"breaker_state": get_anchor_breaker().state.value}


@router.post("/nira-kill")
async def nira_kill() -> dict[str, object]:
    _ensure_enabled()
    get_nira_breaker().force_open()
    return {"breaker_state": get_nira_breaker().state.value}


@router.post("/nira-restore")
async def nira_restore() -> dict[str, object]:
    _ensure_enabled()
    get_nira_breaker().force_close()
    return {"breaker_state": get_nira_breaker().state.value}


@router.post("/flush-anchor/{district_id}")
async def demo_flush(district_id: int) -> dict[str, object]:
    _ensure_enabled()
    return await flush_district(district_id, force=True)


@router.post("/rescore-pending")
async def rescore_pending() -> dict[str, object]:
    _ensure_enabled()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM transfers WHERE status = 'PENDING' ORDER BY initiated_at DESC LIMIT 50"
        ).fetchall()
    count = 0
    for r in rows:
        await enqueue_score(subject_type="TRANSFER", subject_id=str(r[0]))
        count += 1
    return {"enqueued": count}


@router.get("/status")
async def demo_status() -> dict[str, object]:
    _ensure_enabled()
    return {
        "demo_mode": True,
        "anchor_breaker": get_anchor_breaker().state.value,
        "nira_breaker": get_nira_breaker().state.value,
    }
