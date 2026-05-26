"""FastAPI entrypoint: middleware, routers, lifespan tasks."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.blockchain.anchor_service import anchor_loop_forever
from app.bootstrap.seed import maybe_seed_on_startup
from app.config import get_settings
from app.database import apply_migrations, close_connections
from app.fraud.worker import consumer_loop_forever, stop_consumer
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.limits import limiter
from app.middleware.request_id import RequestIdMiddleware
from app.routers import (
    admin,
    anchors,
    demo,
    disputes,
    fraud,
    health,
    nira,
    owners,
    parcels,
    titles,
    transfers,
    ussd,
    verify,
)

logger = logging.getLogger(__name__)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.assert_prod_safety()
    apply_migrations()

    # In non-production (staging / demo / dev) start with showcase data
    # already in place so the public Anchors page and the role-gated
    # dashboards aren't empty. No-op in production and idempotent on
    # warm restarts.
    try:
        maybe_seed_on_startup(settings)
    except Exception:
        logger.exception("seed_on_startup_failed")

    if settings.otel_enabled:
        try:
            from app.tracing import setup_otel

            setup_otel(app)
        except Exception:
            logger.exception("otel_setup_failed")

    anchor_task = asyncio.create_task(anchor_loop_forever(), name="anchor-loop")
    fraud_task = asyncio.create_task(consumer_loop_forever(), name="fraud-consumer")
    logger.info(
        "lifespan_started",
        extra={
            "blockchain_provider": settings.blockchain_provider,
            "nira_provider": settings.nira_provider,
        },
    )
    try:
        yield
    finally:
        stop_consumer()
        anchor_task.cancel()
        fraud_task.cancel()
        for t in (anchor_task, fraud_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        close_connections()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LandGuard Uganda",
        version="0.1.0",
        description=(
            "Blockchain-Enhanced Land Administration & Titling Support System.\n"
            "Off-chain hash-chained ledger + on-chain Merkle anchor."
        ),
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health.router)
    app.include_router(verify.router)  # public, no auth
    app.include_router(ussd.router)    # public, no auth — USSD + SMS verifier
    app.include_router(parcels.router)
    app.include_router(titles.router)
    app.include_router(owners.router)
    app.include_router(transfers.router)
    app.include_router(disputes.router)
    app.include_router(anchors.router)
    app.include_router(fraud.router)
    app.include_router(nira.router)
    app.include_router(admin.router)
    # Demo control panel is intended for the showcase storyboard
    # (Acts 1–5). Gate on app_env only: any non-production deploy can
    # serve it. Per-endpoint guards in demo.py still check app_env,
    # and Settings.assert_prod_safety() ensures demo_mode is false in
    # production deploys, so a real production environment can never
    # reach this branch.
    if settings.app_env != "production":
        app.include_router(demo.router)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_request_error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={
                "detail": "internal server error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    return app


app = create_app()
