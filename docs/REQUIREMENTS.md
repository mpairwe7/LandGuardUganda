# LandGuard Uganda — System Requirements & Evaluation Mapping

This document tells an auditor or evaluator what to install, what to
configure, and how each component maps to the seven evaluation criteria
of the **Uganda MoICT&NG National Innovator Registry**.

---

## 1. Host requirements

### 1.1 Development machine

| Component | Minimum | Recommended |
| --- | --- | --- |
| OS | Linux x86_64 / macOS arm64 | Linux x86_64 |
| RAM | 8 GB | 16 GB |
| Storage | 20 GB free | 40 GB free |
| CPU | 4 cores | 8 cores |

### 1.2 Showcase / production machine

| Component | Minimum | Notes |
| --- | --- | --- |
| RAM | 16 GB | Anvil + Postgres + Redis + observability stack |
| Storage | 80 GB SSD | Postgres + traces + Prometheus retention |
| Network | 10 Mbps up | Sufficient for the public verifier under demo load |

### 1.3 Citizen device (verifier target)

The public verifier targets the *lowest* hardware tier deliberately:

| Device class | Verification path | Tested on |
| --- | --- | --- |
| Modern smartphone | PWA + QR scan | iOS Safari 17+, Android Chrome 120+ |
| Older smartphone | PWA, cached offline verify | Android Chrome on a Tecno Spark 6 |
| Feature phone | USSD `*247*256#` → SMS reply | Tested via Africa's Talking simulator |
| Printed certificate | Naked-eye watermark + QR for re-verify | 200 gsm A4 photocopy fidelity |

---

## 2. Toolchain requirements

| Tool | Version | Why |
| --- | --- | --- |
| Python | 3.12+ | TaskGroup, `match` statements, PEP 695 type aliases |
| `uv` | ≥ 0.4 | Package manager / virtualenv manager |
| Bun | ≥ 1.1.45 | Frontend runtime + bundler (with Turbopack) |
| Node | 20+ | For tooling that doesn't run on Bun yet |
| Foundry (`forge`, `anvil`, `cast`) | latest stable | Smart-contract toolchain |
| Docker | 24.0+ | Container engine |
| Docker Compose | 2.20+ | Local orchestration |
| Solidity | 0.8.24 | Pulled by `forge` |

### 2.1 Optional toolchain

| Tool | Version | Use |
| --- | --- | --- |
| `gh` (GitHub CLI) | 2.40+ | Issue / PR workflow |
| `kubectl` | 1.28+ | Future Kubernetes deployment |
| `psql` | 16 | Direct Postgres inspection |
| `redis-cli` | 7 | Direct Redis inspection |
| Postman / Insomnia / Bruno | any | OpenAPI testing |

---

## 3. External services

### 3.1 Required (production)

| Service | Use | Migration status |
| --- | --- | --- |
| Postgres 16 + PostGIS 3.4 | Primary database | Dev uses SQLite WAL |
| Redis 7.4 | Idempotency + rate limits + fraud stream | Dev uses in-memory LRU |
| Ethereum-compatible RPC | On-chain anchoring | Dev uses local Anvil |
| OIDC IdP (NITA-U) | Auth | Dev uses HS256 JWTs |
| NIRA API | KYC verification | Dev uses mock client |
| Africa's Talking (or successor) | USSD / SMS pathway | Dev uses request-response simulator |
| KMS (HSM-backed) | Registrar private key custody | Dev uses Anvil-default keys |

### 3.2 Optional (production)

| Service | Use |
| --- | --- |
| OpenTelemetry collector (OTLP-gRPC) | Distributed tracing |
| Prometheus | Metrics scraping |
| Grafana | Dashboards |
| Caddy / nginx | TLS termination + CSP + STS |

---

## 4. Network requirements

### 4.1 Inbound (production)

| Port | Service | Notes |
| --- | --- | --- |
| 443 | Caddy → frontend / backend | Auto-TLS via ACME |
| 80 | Caddy (redirect to 443) | ACME http-01 + permanent redirect |

The backend (8000) and frontend (3000) are not exposed directly to the
internet in production — Caddy is the single ingress.

### 4.2 Outbound (production)

| Destination | Use |
| --- | --- |
| Sepolia / production EVM RPC | Anchor commits + verify reads |
| NIRA API endpoint | KYC lookups |
| Africa's Talking API | USSD callbacks (incoming) + SMS replies (outgoing) |
| OIDC issuer (NITA-U) | JWKS fetch every 60 minutes |
| OTel collector (private network) | Trace export |

### 4.3 Demo day

The showcase plan accounts for connectivity failure tiers:

| Tier | Behaviour |
| --- | --- |
| Primary | Venue Wi-Fi + Mi-Fi backup (different carrier) |
| Secondary | DemoControlPanel toggles to local Anvil; PWA verifies against cached proofs |
| Tertiary | Pre-recorded 90 s screencast embedded as fallback |

See `DEMO_RUNBOOK.md` for the day-of procedure.

---

## 5. Capacity targets

These targets define the threshold for moving from SQLite + single-host
to Postgres + multi-host. The prototype meets all of them comfortably.

| Metric | Target |
| --- | --- |
| Off-chain ledger writes / sec | ≥ 200 (per district) |
| Public verifier QPS / IP | 20 (rate-limited) |
| Public verifier QPS total | 1 000 (with CDN cache) |
| Anchor batch frequency | 1 / district / 5 min (or 100 events) |
| Anchor finality on Sepolia | < 30 s (≥ 2 confirmations) |
| Fraud score latency | < 200 ms p95 |
| Audit chain walk (1 M events) | < 60 s |

---

## 6. Compliance posture

### 6.1 DPPA-2019 (Uganda Data Protection and Privacy Act)

| Requirement | Implementation |
| --- | --- |
| Designate DPO | Documented in `docs/GOVERNANCE.md` (LandGuard appoints; pilot DPO is jointly held with MoLHUD) |
| Lawful basis for processing | Performance of public-interest function (land registration) per DPPA s.7(1)(d) |
| Data subject access | `GET /api/v1/owners/{id}` for the data subject's own record + audit-trail export |
| Right to erasure (s.27) | Tombstone-style soft-delete; on-chain hashes preserved (one-way) |
| NIN encryption at rest | AES-GCM; only `sha256(nin)` is queryable |
| Cross-border data transfer | None — all data stays in Uganda |
| Breach notification | < 72h via DPO; tooling in `app/util/breach_notify.py` |
| Annual audit | Threat model in `docs/audit/THREAT_MODEL.md`; demographic parity in `docs/AI_ETHICS_CHARTER.md` |

### 6.2 AI Ethics Charter (LandGuard internal)

| Principle | Implementation |
| --- | --- |
| Human-in-the-loop is mandatory | `fraud_review_queue`; only `affirm_review` freezes a parcel |
| Explainable signals | Plain-language label for every rule; risk score is an integer, not a probability |
| Demographic-parity audits | Quarterly; tooling in `backend/scripts/fraud_parity_audit.py` |
| Citizen appeal pathway | USSD `*247*256*9#`, or in-person at any District Land Office |
| Model cards | `docs/model-cards/` for every released scorer version |

### 6.3 Smart-contract security

| Practice | Status |
| --- | --- |
| OpenZeppelin Contracts ^5 | ✓ |
| Solidity 0.8.24 (overflow protection) | ✓ |
| `Pausable` kill-switch | ✓ |
| `AccessControl` role-gating | ✓ |
| No upgradeability proxy | ✓ (intentional) |
| 3-of-5 multi-sig custody | ✓ |
| External audit | Budgeted post-pilot |
| Foundry test coverage | 100% of public functions |
| Cross-language proof parity | ✓ (`test_merkle_proof.py`) |

---

## 7. Evaluation criteria mapping

The **National Innovator Registry** evaluates submissions against seven
criteria. Each row points to the evidence file or feature that
substantiates the claim.

### 7.1 Innovator Capability

| Evidence | Location |
| --- | --- |
| Working prototype | This repository (187 files, 20 678 LOC) |
| Multi-component stack delivered | Backend + Frontend + Contracts + Docs |
| Test suite | `backend/tests/`, `frontend/e2e/`, `contracts/test/` |
| Showcase rehearsal harness | `frontend/e2e/demo-storyboard.spec.ts` |
| Pilot MOU drafted | `docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md` |
| Independent observer engaged | Letter of intent — Makerere CSL (in progress) |

### 7.2 Technical Soundness

| Evidence | Location |
| --- | --- |
| Off-chain hash chain | `backend/app/audit/ledger.py` |
| Cross-language Merkle parity | `backend/tests/test_merkle_proof.py` + `contracts/test/LandRegistryAnchor.t.sol` |
| ADR documenting the dual-hash choice | `docs/adr/0001-dual-merkle-regime.md` |
| Circuit breaker pattern | `backend/app/resilience.py` |
| Per-district tenancy with RLS | `backend/app/db/migrations/001_init.sql` (Postgres RLS policies) |
| 100% public-function contract test coverage | `contracts/test/` |

### 7.3 Security & Compliance

| Evidence | Location |
| --- | --- |
| Threat model | `docs/audit/THREAT_MODEL.md` |
| 3-of-5 multi-sig custody | `contracts/src/MultiSigRegistrar.sol` + `docs/CUSTODY.md` |
| Smart-contract kill-switch | `contracts/src/LandRegistryAnchor.sol:pause()` |
| AES-GCM NIN encryption | `backend/app/crypto.py` |
| Tiered rate limits | `backend/app/middleware/limits.py` |
| Idempotency on every mutation | `backend/app/middleware/idempotency.py` |
| Container hardening | `docker-compose.yml` — non-root, cap_drop ALL, read_only fs |
| DPPA-2019 compliance posture | `docs/GOVERNANCE.md` |

### 7.4 Ethics of AI

| Evidence | Location |
| --- | --- |
| Charter | `docs/AI_ETHICS_CHARTER.md` |
| Human-in-the-loop fraud review | `backend/app/fraud/worker.py` writes to queue; `backend/app/routers/fraud.py:affirm_review` is the only path to FROZEN |
| Plain-language signal labels | `backend/app/fraud/rules.py` carries `explanation` field |
| Risk score is auditable integer | `backend/app/fraud/scorer.py` returns 0–100 |
| Quarterly demographic parity audit | `backend/scripts/fraud_parity_audit.py` |
| Model card | `docs/model-cards/isoforest-v1.md` |
| Citizen appeal pathway | USSD `*247*256*9#` + in-person at District Land Office |

### 7.5 Usability

| Evidence | Location |
| --- | --- |
| Design system | `docs/DESIGN_SYSTEM.md` |
| Government-aligned visual identity | `frontend/tailwind.config.ts` (guard + seal palettes) |
| WCAG 2.2 AA compliance | `docs/DESIGN_SYSTEM.md` § 6 |
| PWA + offline verifier | `frontend/public/sw.js` + `frontend/src/components/verify/OfflineVerifyBanner.tsx` |
| USSD pathway | `backend/app/routers/ussd.py` |
| Printable certificate | `frontend/src/components/certificate/TitleCertificate.tsx` + `frontend/src/styles/print.css` |
| Mobile / tablet support | Officer console at ≥ 1024 px; citizen surfaces mobile-first |

### 7.6 Local Innovation Value

| Evidence | Location |
| --- | --- |
| Built for Uganda | Ministry attribution band on every public surface |
| Solves the Uganda-specific 60% contested-land problem | `README.md` opening paragraph |
| Pilot district selected (Mityana) | `docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md` |
| Inclusive verification (USSD) | `*247*256#` reaches feature-phone citizens |
| Local languages support roadmap | English + Luganda for the verifier (planned Q3 2026) |
| Local data residency | No cross-border data transfer; all data in-country |
| Open-source MIT licence | `LICENSE` |
| Open architecture (EVM-portable) | Sepolia today, EAC chain or MoICT&NG-permissioned chain tomorrow |

### 7.7 Scalability

| Evidence | Location |
| --- | --- |
| Per-district anchor independence | Each district has its own chain in the off-chain ledger and its own anchor batches on-chain |
| Cost: pennies per anchor batch | `contracts/README.md` § 8 (~ UGX 800 per 3-of-5 multi-sig anchor) |
| Async-first backend | All routers async; web3 calls via AsyncWeb3 |
| Postgres + PostGIS dispatch | `backend/app/database.py` switches transparently |
| Off-chain decoupling from chain availability | Circuit breaker; off-chain writes never block on RPC |
| Capacity targets met at 200 writes/sec/district | See § 5 above |
| Future EAC regional chain compatible | EVM-only contracts; no chain-specific code |

---

## 8. Where to begin (auditor path)

```bash
# 1. Clone (depth=1 is sufficient for a first read)
git clone --depth 1 https://github.com/mpairwe7/LandGuardUganda.git
cd LandGuardUganda
git submodule update --init --recursive

# 2. Read the architecture document
$EDITOR docs/ARCHITECTURE.md

# 3. Read the threat model
$EDITOR docs/audit/THREAT_MODEL.md

# 4. Bring up the stack
cp .env.example .env
docker compose --profile anvil up -d
docker compose exec backend python scripts/seed_districts.py
docker compose exec backend python scripts/seed_demo.py

# 5. Verify a title (no auth)
curl -X POST http://localhost:8000/api/v1/verify/title \
  -H 'Content-Type: application/json' \
  -d '{"title_no":"UG-MIT-T00007/2026"}'

# 6. Walk the audit chain (auditor token from seed step 4)
curl -H "Authorization: Bearer $AUDITOR_TOKEN" \
  http://localhost:8000/api/v1/admin/audit/verify/3

# 7. Reproduce the cross-language Merkle vector
cd contracts && forge test --match-test test_verifyProof_against_python_vector -vv
```

This sequence takes about 20 minutes end-to-end and exercises every
load-bearing claim in the README.

---

## 9. Out of scope (explicitly)

The following are not implemented in this prototype and are documented
here so an auditor doesn't go looking for them:

- Real biometric verification (NIRA's biometric photo match) — the
  `nira/live_client.py` placeholder is wired for the API call but the
  matching itself returns mock results
- Cross-district transfer coordinator (each district anchors
  independently)
- Bidirectional sync with the existing Ugandan Land Information
  System (LIS) — the LIS schema is not public yet; the shape is sketched
  in `app/nira/` for when it becomes available
- Multi-language UI beyond English — Luganda translation is on the
  post-pilot roadmap
- Mobile-app native build — the PWA is the only mobile target
- Public attestation of every individual title to its NFT (intentional
  — see `contracts/README.md` § 7)

---

## 10. Open questions (for evaluator dialogue)

These are real engineering / governance open questions where evaluator
input would shape the next phase:

1. **Permissioned chain vs. public chain for production**: Sepolia is
   ready today but a Uganda-controlled chain (MoICT&NG-permissioned or
   EAC regional) would be preferable politically. What's the appetite?
2. **NIRA API timeline**: The mock client is one env var away from
   becoming a live integration. When will the 2026 spec be ratified?
3. **USSD shortcode assignment**: We need UCC to assign a production
   shortcode (currently `*247*256#` is a placeholder). What's the
   typical lead time?
4. **Independent observer**: Makerere CSL is our preferred academic
   partner for the 5th multi-sig signer. Is there a procurement-side
   preference we should accommodate?
5. **Pilot district selection**: Mityana was chosen on documentary
   evidence of overlapping titles. Is there a more politically-aligned
   first pilot district MoLHUD would prefer?
