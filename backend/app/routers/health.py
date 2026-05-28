"""Liveness, readiness, and Prometheus metrics endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.audit.verifier import verify_chain
from app.blockchain import get_blockchain_client
from app.blockchain.anchor_service import get_anchor_breaker
from app.config import get_settings
from app.database import get_connection
from app.util.cache import get_redis

router = APIRouter(tags=["ops"])

_FRAUD_MODEL_PATH = Path(__file__).resolve().parent.parent / "fraud" / "training" / "isoforest-v1.joblib"


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

    # Fraud scorer model presence — surfaced so reviewers can see if the
    # IsolationForest joblib is loaded vs the rules-only fallback path.
    # ``scorer.score_subject`` works in both modes; this is informational.
    details["fraud_model"] = {
        "loaded": _FRAUD_MODEL_PATH.exists(),
        "path": str(_FRAUD_MODEL_PATH),
    }

    # Audit-chain integrity, per-district. Walks the chain and reports the
    # most-corrupt district (if any). Cheap on the small districts of the
    # Mityana pilot; cap event-walk depth via the ledger's own limit. If
    # any district fails verification we mark readiness as degraded but
    # still return 200 — the dataset is broken but the service is up and
    # an auditor needs the endpoint to triage.
    try:
        chain_reports: list[dict[str, object]] = []
        any_corrupt = False
        for did in (1, 2, 3, 4):
            r = verify_chain(tenant_id=str(did))
            chain_reports.append({
                "district_id": did,
                "events": int(r.total_events),
                "verified": bool(r.verified),
            })
            if not r.verified and r.total_events > 0:
                any_corrupt = True
        details["audit_chain"] = {
            "verified": not any_corrupt,
            "districts": chain_reports,
        }
        if any_corrupt:
            payload["degraded"] = True
    except Exception as exc:
        details["audit_chain"] = f"error: {exc}"

    payload["details"] = details
    if not payload["ok"]:
        response.status_code = 503
    return payload


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
