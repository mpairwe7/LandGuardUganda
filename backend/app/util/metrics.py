"""Prometheus metrics — exposed at ``/metrics``.

Counters and gauges named to match the alerting policies in
``monitoring/prometheus/alerts.yml``.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# --- Anchor service ---
anchor_batches_total = Counter(
    "anchor_batches_total",
    "Merkle-root anchor batches submitted to the blockchain.",
    ["district_id", "result"],
)
anchor_failures_total = Counter(
    "anchor_failures_total",
    "Anchor submissions that failed before chain confirmation.",
    ["reason"],
)
anchor_breaker_open = Gauge(
    "anchor_breaker_open",
    "1 if the blockchain circuit breaker is OPEN, else 0.",
)
anchor_queue_depth = Gauge(
    "anchor_queue_depth",
    "Unanchored audit events per district.",
    ["district_id"],
)

# --- NIRA ---
nira_calls_total = Counter(
    "nira_calls_total",
    "NIRA verification calls by result.",
    ["result"],
)
nira_breaker_open = Gauge(
    "nira_breaker_open",
    "1 if the NIRA circuit breaker is OPEN, else 0.",
)

# --- Fraud ---
fraud_scores_total = Counter(
    "fraud_scores_total",
    "Fraud scores produced by the scorer.",
    ["action"],
)
fraud_blocks_total = Counter(
    "fraud_blocks_total",
    "Transfers blocked because risk_score >= 75.",
)

# --- Audit ---
audit_failure_total = Counter(
    "audit_failure_total",
    "Audit ledger appends that crashed and were swallowed.",
)

# --- HTTP ---
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Request duration histogram.",
    ["method", "route", "status"],
)
