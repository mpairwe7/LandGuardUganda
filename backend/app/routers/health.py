"""Liveness, readiness, and Prometheus metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.blockchain import get_blockchain_client
from app.blockchain.anchor_service import get_anchor_breaker
from app.config import get_settings
from app.database import get_connection
from app.util.cache import get_redis

router = APIRouter(tags=["ops"])


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, object]:
    return {"ok": True, "app": get_settings().app_name}


@router.get("/readyz", include_in_schema=False)
async def readyz(response: Response) -> dict[str, object]:
    settings = get_settings()
    payload: dict[str, object] = {"app": settings.app_name, "ok": True, "details": {}}
    details: dict[str, object] = {}

    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        details["db"] = "ok"
    except Exception as exc:
        details["db"] = f"error: {exc}"
        payload["ok"] = False

    try:
        redis = await get_redis()
        details["redis"] = "ok" if redis is not None else "fallback"
    except Exception as exc:
        details["redis"] = f"error: {exc}"

    try:
        client = get_blockchain_client()
        chain = await client.health()
        details["blockchain"] = chain
        breaker = get_anchor_breaker()
        details["anchor_breaker"] = breaker.state.value
    except Exception as exc:
        details["blockchain"] = f"error: {exc}"
        # Blockchain down does NOT make readiness fail — the architectural
        # promise is that off-chain operations keep working when the chain
        # is unreachable. We surface "degraded" without 503.
        payload["degraded"] = True

    payload["details"] = details
    if not payload["ok"]:
        response.status_code = 503
    return payload


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
