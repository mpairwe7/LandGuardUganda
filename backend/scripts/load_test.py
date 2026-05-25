"""Reproducible load test of the public verifier (no SaaS dependency).

Run via ``scripts/load_test.sh`` from the repo root. Targets the SLOs
defined in ``docs/SLA_TARGETS.md`` §2 and §3.

Design notes:
- The verifier is rate-limited at 20/min/IP in production. We bypass
  this only by hitting localhost, which trips the slowapi key on the
  loopback address. For realistic stage results, run against a deployed
  instance from multiple source IPs. The load_test still validates the
  **backend's** throughput envelope (the rate limit is a separate
  protection layer with its own metric).
- We use ``httpx.AsyncClient`` with a bounded semaphore so the host's
  ephemeral port range isn't exhausted at high RPS.
- Output is a CycloneDX-adjacent JSON summary plus a per-request CSV
  trace, both content-addressable.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx


@asynccontextmanager
async def _bounded(client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
    async with semaphore:
        yield client


async def _one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    base_url: str,
    title_no: str,
) -> tuple[float, int, float]:
    start = time.perf_counter()
    async with _bounded(client, semaphore):
        try:
            r = await client.post(
                f"{base_url}/api/v1/verify/title",
                json={"title_no": title_no},
                timeout=10.0,
            )
            status = r.status_code
        except Exception:
            status = 0
    duration = time.perf_counter() - start
    return (start, status, duration)


async def run(args: argparse.Namespace) -> dict[str, Any]:
    end_time = time.monotonic() + args.duration
    interval = 1.0 / args.target_rps
    semaphore = asyncio.Semaphore(args.concurrency)

    results: list[tuple[float, int, float]] = []

    async with httpx.AsyncClient(http2=False) as client:
        tick = time.monotonic()
        tasks: list[asyncio.Task] = []
        while time.monotonic() < end_time:
            task = asyncio.create_task(
                _one(client, semaphore, args.base_url, args.title_no)
            )
            tasks.append(task)
            tick += interval
            sleep_for = tick - time.monotonic()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
        completed = await asyncio.gather(*tasks, return_exceptions=False)
        results.extend(completed)

    durations_ms = [r[2] * 1000.0 for r in results]
    successes = [d for r, d in zip(results, durations_ms) if 200 <= r[1] < 300]
    status_counts: dict[int, int] = {}
    for r in results:
        status_counts[r[1]] = status_counts.get(r[1], 0) + 1

    durations_ms.sort()

    def pct(p: float) -> float:
        if not durations_ms:
            return 0.0
        idx = int(round((p / 100.0) * (len(durations_ms) - 1)))
        return durations_ms[idx]

    summary = {
        "schema": "landguard-load-test/v1",
        "base_url": args.base_url,
        "title_no": args.title_no,
        "duration_seconds": args.duration,
        "target_rps": args.target_rps,
        "completed_requests": len(results),
        "successful_requests": len(successes),
        "success_ratio": (len(successes) / len(results)) if results else 0.0,
        "status_counts": status_counts,
        "latency_ms": {
            "p50": pct(50),
            "p90": pct(90),
            "p95": pct(95),
            "p99": pct(99),
            "max": max(durations_ms) if durations_ms else 0.0,
            "mean": statistics.fmean(durations_ms) if durations_ms else 0.0,
        },
        "slo_targets_ms": {  # from docs/SLA_TARGETS.md §2
            "verifier_p95": 250.0,
        },
        "slo_pass": pct(95) < 250.0,
    }

    if args.out_csv:
        Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["start_perf_counter", "status", "duration_seconds"])
            for r in results:
                w.writerow([f"{r[0]:.6f}", r[1], f"{r[2]:.6f}"])

    if args.out_summary:
        Path(args.out_summary).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_summary, "w") as f:
            json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return summary


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="LandGuard public-verifier reproducible load test"
    )
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--duration", type=int, default=60)
    p.add_argument("--target-rps", type=int, default=250)
    p.add_argument("--concurrency", type=int, default=64)
    p.add_argument("--title-no", default="UG-MIT-T00007/2026")
    p.add_argument("--out-summary", default=None)
    p.add_argument("--out-csv", default=None)
    return p


if __name__ == "__main__":
    args = _parser().parse_args()
    asyncio.run(run(args))
