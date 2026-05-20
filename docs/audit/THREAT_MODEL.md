# Threat Model

A condensed STRIDE-style model focused on the assets that matter most:
**land title authenticity**, **citizen PII (NIN)**, and **on-chain custody
keys**.

## Assets

| Asset | Confidentiality | Integrity | Availability |
|---|---|---|---|
| Title certificates | Public | **Critical** | High |
| Audit chain (off-chain) | Internal | **Critical** | High |
| On-chain anchor | Public | **Critical** | Medium (chain dependency) |
| Citizen NIN | **High** | High | Medium |
| Multi-sig signer keys | **Critical** | **Critical** | High |
| Fraud-scorer model | Internal | High | Low |

## Adversaries

| Adversary | Motive | Capability |
|---|---|---|
| Forging broker | Profit (land grab) | Submit forged transfer, attempt collusion with a corrupt officer |
| Compromised registrar | Coercion / bribe | Mint titles, attempt to alter records |
| Insider DB admin | Coercion / sabotage | Direct SQL access |
| External cyber actor | Theft / disruption | Network access, attempt to exhaust resources |
| Supply-chain attacker | Persistent access | Plant malicious dependency, compromise CI |

## Threat → Mitigation Matrix (selected)

| Threat | Mitigation |
|---|---|
| Forged title submitted off-chain | Title-issuance only by REGISTRAR role; every issuance is hash-chained and Merkle-anchored within 5 minutes; public verifier will not validate a forged title because its leaf hash differs |
| Single-key registrar compromise | 3-of-5 ``MultiSigRegistrar``: no single key can anchor; see ``docs/CUSTODY.md`` |
| DB admin alters audit_events row | Chain verifier (``app/audit/verifier.py``) detects the mismatch; anchored Merkle root differs from recomputed root |
| Bribed officer affirms a fraudulent ``BLOCK`` dismissal | Citizen appeal pathway (``POST /api/v1/fraud/appeals``); appeal resolved by AUDITOR or different REGISTRAR; quarterly parity audit catches systematic bias |
| Replay of a captured commit transaction | ``commitBatch`` rejects duplicate batchId (``DuplicateBatch`` revert) |
| Smart-contract bug | ``LandRegistryAnchor.pause()`` kill switch; new anchors halt while a fix is deployed; existing anchors remain valid (immutable on-chain) |
| RPC outage | Circuit-breaker on the anchor client; off-chain writes continue; queued batches drain on recovery |
| NIN exposed via logs | All log statements pass NIN through ``sha256_hex``; raw NIN stored AES-GCM encrypted in ``owners.nin_encrypted``; decryption gated by audit-emitting role check |
| USSD/SMS abuse (scraping titles) | Rate-limited at 20/min/IP; phone-hash frequency analysis in the audit chain; verification returns no PII, only validity status |
| Demographic-bias amplification by fraud rules | Quarterly parity audit; rule weights zeroed automatically if a group exceeds 1.5× mean flag rate (``docs/AI_ETHICS_CHARTER.md`` §5) |
| Lost / leaked multisig signer key | Quarterly key rotation; ≤ 2 simultaneous-compromise tolerance under 3-of-5 threshold; emergency pause via ``DEFAULT_ADMIN_ROLE`` |
| Compromised dependency (supply chain) | Locked dependencies in ``uv.lock`` / ``bun.lock``; ``forge`` audit of Solidity dependencies; SBOM published in ``docs/sbom.json`` (TODO) |
| Operator shuts down LandGuard | On-chain anchors remain verifiable independently; off-chain ledger handed over to MoLHUD on pilot termination (MOU §7.2); printed title QR codes still verify against the chain without LandGuard's service |

## Out of scope (declared)

- Side-channel attacks on HSMs (delegated to NITA-U procurement standards).
- Coercion of citizens to file false appeals (sociotechnical mitigation:
  appeal volume reviewed quarterly; outlier districts flagged).
- Compromise of the underlying EVM chain itself (in production we plan to
  migrate to a Ugandan permissioned chain to reduce this risk; see
  ``docs/ARCHITECTURE.md`` migration notes).
