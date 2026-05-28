# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir uv==0.4.* && \
    useradd --create-home --uid 10001 landguard

WORKDIR /app
COPY pyproject.toml README.md ./
RUN uv pip install --system .

COPY app ./app
COPY scripts ./scripts

# Per mpairwe7/MLOPS_V1 Crane Cloud deployment pattern (Dockerfile.cpu
# line 121: `mkdir -p <writable dirs> && chown -R <user>:<user> /app`).
# Without this Crane Cloud's pod crashes immediately with PermissionError —
# apply_migrations() can't create the SQLite WAL, joblib can't load the
# trained model, anchor_service can't write contract_address.json.
RUN mkdir -p /app/data_store /app/app/fraud/training \
    && chown -R landguard:landguard /app

USER landguard
EXPOSE 8000

# start-period=60s matches MLOPS_V1's Crane Cloud pattern — gives the pod
# time to apply migrations + load the IsolationForest joblib + bind 0.0.0.0
# before Crane Cloud's readiness probe declares it failed.
HEALTHCHECK --interval=15s --timeout=3s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# --no-server-header so uvicorn's protocol layer doesn't overwrite the
# SecurityHeadersMiddleware "Server: landguard" header with "Server: uvicorn".
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
