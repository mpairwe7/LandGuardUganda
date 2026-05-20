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
COPY pyproject.toml ./
RUN uv pip install --system .

COPY app ./app
COPY scripts ./scripts

USER landguard
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
