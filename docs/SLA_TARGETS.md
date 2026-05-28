# Service Level Targets

The targets below define **what good looks like** for the LandGuard
pilot and what *national scale* would require. Targets are written as
SLO-style budgets (objective + measurement window + measurement method)
so an evaluator can audit them against Prometheus metrics in
`monitoring/prometheus/prometheus.yml`.

---

## 1. Tiered availability targets

| Tier | What it covers | Availability SLO (monthly) | Error budget |
|---|---|---:|---:|
| T1 Public verifier (`/api/v1/verify/title`, `/api/v1/ussd`) | The citizen-facing read path | **99.9%** | 43 min/month |
| T2 Off-chain writes (parcels, titles, transfers) | Officer / Registrar console | **99.5%** | 3h 36m/month |
| T3 On-chain anchor commits | Background batched writes | **99.0%** (per district, monthly) | — — degradation queues, never blocks T1/T2 |
| T4 Demo control panel | Showcase only | best-effort | N/A |

**Architectural rationale:** the public verifier (T1) is critical
because a failed verification destroys trust; the on-chain anchor (T3)
is intentionally permitted to degrade because the circuit breaker
ensures off-chain writes survive chain outages.

---

## 2. Latency targets (p95 unless noted)

| Path | Target | Measured by |
|---|---:|---|
| Public verifier (online lookup) | < 250 ms | `http_request_duration_seconds{route="/api/v1/verify/title"}` |
| Public verifier (offline bundle) | < 50 ms | same histogram, distinct label set |
| USSD round-trip | < 2.5 s (carrier ceiling) | Africa's Talking simulator + production traces |
| Officer affirm action | < 500 ms | `/api/v1/fraud/review/{id}/affirm` |
| Anchor commit (Anvil) | < 5 s | `anchor_batches_total{result}` + transaction-receipt histogram |
| Anchor commit (Sepolia) | < 30 s | same |
| Anchor commit (3-of-5 multi-sig) | < 8 s with auto co-signer | same |
| Audit chain walk (1M events) | < 60 s | `scripts/verify_audit_chain.py` runtime |

---

## 3. Capacity targets (national rollout, modelled)

| Metric | Pilot (Mityana) | National (146 districts) |
|---|---:|---:|
| Off-chain writes / sec / district | 200 (sustained) | 200 × 146 = **29,200 sustained** |
| Active parcels | ≈ 50,000 | ≈ 8M (UBOS census-projected) |
| Active titles | ≈ 25,000 | ≈ 4M |
| Anchor batches / day / district | ≈ 50 | 7,300 nationally |
| Public verifications / day | ≈ 5,000 | ≈ 250,000 |
| Storage | ≈ 5 GB | ≈ 800 GB (with WAL retention) |

**Scaling lever from prototype → national:**

```
SQLite WAL              →  Postgres 16 + PostGIS 3.4 (already supported)
                          DB_BACKEND=postgres
Single-process backend  →  Horizontal pod autoscale on K8s
                          uvicorn workers=8 per pod, 4–16 pods
Single anchor worker    →  Per-district worker partitioning
                          (per-tenant mutex already in `app/audit/ledger.py`)
Single RPC endpoint     →  Multi-endpoint failover via web3 middleware
```

None of these require code change — they are pure deployment moves.
That is the architectural payoff.

---

## 4. Cost-of-availability targets

| Cost dimension | Pilot Y1 | National Y3 (modelled) |
|---|---:|---:|
| Infra (compute + storage + network) | UGX 8M / year | UGX ≈ 180M / year |
| RPC + chain fees | UGX 4M / year | UGX ≈ 4M / year (permissioned chain hosted internally) |
| USSD carrier traffic (50% of verifications) | UGX 3M / year | UGX ≈ 540M / year (citizen-borne; not platform cost) |
| Operational staffing | UGX 60M / year | UGX ≈ 850M / year (15 FTE) |
| **Platform cost / citizen / year** | UGX 1.5 / citizen / year (pilot) | UGX ≈ 25 / citizen / year (national steady-state) |

For comparison, the **average court-litigated land dispute in Uganda
costs UGX 2.5M to UGX 8M** (Uganda Law Society 2023 estimate). Preventing
even 0.1% of titles from going to dispute via early fraud detection
covers the entire national platform cost.

---

## 5. Observability targets

| Signal | Source | Alert threshold |
|---|---|---|
| `anchor_batches_total{result="FAILED"}` | Prometheus | > 0 over 15 min |
| `anchor_breaker_open` | Prometheus | == 1 over 5 min |
| `nira_breaker_open` | Prometheus | == 1 over 5 min |
| `audit_failure_total` | Prometheus | > 0 over 1 min |
| `fraud_blocks_total` rate | Prometheus | sudden 10× change vs trailing 24 h |
| Per-route `http_request_duration_seconds` p95 | Prometheus | breach of §2 targets |
| `anchor_queue_depth{district_id}` | Prometheus | > 500 over 30 min (chain backed up) |

Grafana dashboard JSON ships in `monitoring/grafana/landguard.json`
(see open gap in `docs/audit/CODEBASE_MAP.md` §8 — landing 2026-05-31).

---

## 6. Incident-response targets

| Severity | Detection target | Acknowledgement | Mitigation | Public-disclosure window |
|---|---:|---:|---:|---:|
| Sev-1 (verifier down, fraud bypass, key compromise) | < 5 min via Prometheus alert | < 15 min | < 4 h (full or workaround) | ≤ 72 h with full post-mortem |
| Sev-2 (anchor stall > 1 h, single-officer console regression) | < 15 min | < 1 h | < 24 h | ≤ 7 days |
| Sev-3 (degraded fraud-scorer parity, model drift) | < 24 h | < 1 business day | by next quarterly review | ≤ 90 days |

Sev-1 + Sev-2 trigger an automatic chain-pause readiness review (the
`LandRegistryAnchor.pause()` kill switch is the last line of defence).

---

## 7. DPPA §19 breach-notification SLA

DPPA 2019 requires the data subject and the Personal Data Protection
Office to be notified within **72 hours** of becoming aware of a breach
likely to result in risk to the rights of natural persons. The runbook:

1. **Detect** (Prometheus alert / audit-chain anomaly / external report).
2. **Triage** within 60 minutes — confirm scope, identify affected
   `nin_hash` set.
3. **Contain** — rotate keys / pause anchors / revoke roles as needed
   under MAINTAINERS.md "Out-of-band escalation".
4. **Notify** PDPO within 72h (template letter in
   `docs/runbooks/dppa-breach-notification.md` — to land 2026-05-31).
5. **Communicate** to affected citizens via SMS + a public statement on
   the LandGuard site. The audit chain records the notification act
   (`BREACH_NOTIFIED` event type).
6. **Post-mortem** within 7 days, public version published.

---

## 8. Climate / sustainability targets

| Dimension | Target |
|---|---|
| Energy intensity of anchor commits | Tied to Polygon PoS (≈ 0.001 kWh per anchor); roughly 4.6 MWh / year nationally — equivalent to a single Ugandan household for 3 years |
| Infra carbon | Pilot hosts with NITA-U-accredited provider committed to ≥ 60% renewable mix by 2027 |
| Hardware longevity | USSD + low-bandwidth-first means we add value to existing feature-phone infrastructure rather than incentivising upgrades |

---

## 9. Continuity targets

- **Quarterly disaster-recovery drill** including audit-chain restore
  from backups (RPO ≤ 24 h; RTO ≤ 4 h for pilot).
- **Annual chain-pause drill** — `LandRegistryAnchor.pause()` exercised
  on Sepolia, fix-and-resume rehearsed.
- **Cold-start documentation** — a new operator can bring the entire
  stack up from a clean clone in ≤ 30 minutes using `QUICKSTART.md`
  alone. Verified in dress rehearsals.

---

## 10. Cross-reference to evidence

| SLO | Evidence script | Sample output |
|---|---|---|
| §2 latency p95 | `bash scripts/load_test.sh` | `evidence/load/*/summary.json` |
| §5 anchor breaker | `curl /readyz` | `readyz_sample.json` |
| §1 verifier availability | `scripts/probe_verifier.py` (single-file, stdlib-only; cron-once or long-running) | `evidence/probes/verifier-availability.csv` |
| §7 breach notification readiness | `docs/runbooks/dppa-breach-notification.md` | runbook + 1 dry-run log |
