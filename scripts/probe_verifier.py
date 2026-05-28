#!/usr/bin/env python3
"""Synthetic availability probe for the LandGuard public verifier.

Backs the **T1 / 99.9 % verifier availability** SLO declared in
``docs/SLA_TARGETS.md``. One sample per ``--interval`` seconds, appended
to a CSV that anyone can audit. Designed to be run under cron, systemd,
or any process manager — the script does **not** daemonise itself.

Each row: ``timestamp_utc, target, http_status, latency_ms, ok``.

USAGE

    # Run once and exit (suitable for ``*/1 * * * *`` cron).
    python scripts/probe_verifier.py --target http://localhost:3000/verify --once

    # Run forever, one sample/minute, appending to the default CSV.
    python scripts/probe_verifier.py

The CSV lives in ``evidence/probes/verifier-availability.csv`` by
default and is gitignored — operators ship the live file to long-term
storage; the repo only ships the schema header so consumers can parse it.

Exit codes (per-sample): 0 if the last sample was OK, 1 otherwise.
"""

from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TARGET = "http://localhost:3000/api/health"
DEFAULT_INTERVAL = 60
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "evidence" / "probes" / "verifier-availability.csv"
HEADER = ["timestamp_utc", "target", "http_status", "latency_ms", "ok"]
TIMEOUT_S = 8.0


def _probe_once(target: str) -> tuple[int | None, float, bool]:
    """Single GET. Returns ``(http_status, latency_ms, ok)``."""
    req = urllib.request.Request(target, headers={"User-Agent": "landguard-probe/1"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            latency_ms = (time.perf_counter() - started) * 1000.0
            status = resp.getcode()
            return status, latency_ms, 200 <= status < 400
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return exc.code, latency_ms, False
    except (urllib.error.URLError, TimeoutError, OSError):
        latency_ms = (time.perf_counter() - started) * 1000.0
        return None, latency_ms, False


def _ensure_csv(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.stat().st_size == 0:
        with out.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(HEADER)


def _append(out: Path, target: str, status: int | None, latency_ms: float, ok: bool) -> None:
    with out.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow([
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            target,
            "" if status is None else int(status),
            round(latency_ms, 1),
            "true" if ok else "false",
        ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default=DEFAULT_TARGET, help=f"URL to probe (default: {DEFAULT_TARGET})")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="seconds between samples (default: 60)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"CSV file to append to (default: {DEFAULT_OUT.relative_to(Path.cwd()) if DEFAULT_OUT.is_relative_to(Path.cwd()) else DEFAULT_OUT})")
    parser.add_argument("--once", action="store_true", help="run a single probe and exit (suitable for cron)")
    parser.add_argument("--max-samples", type=int, default=0, help="stop after N samples (0 = forever)")
    args = parser.parse_args(argv)

    _ensure_csv(args.out)

    stopped = False

    def _stop(_signum, _frame) -> None:  # pragma: no cover — signal handler
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    last_ok = True
    samples = 0
    while not stopped:
        status, latency_ms, ok = _probe_once(args.target)
        _append(args.out, args.target, status, latency_ms, ok)
        last_ok = ok
        samples += 1
        if args.once or (args.max_samples and samples >= args.max_samples):
            break
        # Sleep in small slices so SIGTERM still wakes us up promptly.
        slept = 0.0
        while slept < args.interval and not stopped:
            time.sleep(min(1.0, args.interval - slept))
            slept += 1.0

    return 0 if last_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
