# Governance & Compliance

LandGuard treats land as **digital public infrastructure** — the controls below
follow that posture.

## Data residency & sovereignty

- All citizen PII (NIN, biometric template) is stored AES-GCM encrypted in
  the LandGuard Postgres database within Uganda. Only the SHA-256 hash leaves
  the database; this is what we anchor to the blockchain.
- The blockchain anchor contains **no PII** — only Merkle roots of audit
  hashes. A foreign chain (Sepolia) is acceptable for the prototype because no
  Ugandan personal data leaves the country.
- Migration path: any EVM-compatible chain can host the contract. A Bank of
  Uganda permissioned chain, a regional EAC chain, or a Ministry-of-Lands
  Hyperledger Besu deployment are all one-config swaps (see
  `backend/app/blockchain/sepolia_client.py` `# MIGRATION` comments).

## Compliance map

| Regulation / Standard | Where it lives |
|---|---|
| Uganda Data Protection and Privacy Act (2019) | NIN encrypted at rest (`app/crypto.py`); subject access via per-owner audit reads; right-to-erasure via `AuditLedger.erasure_tombstone` |
| NIST AI Risk Management Framework | Fraud scorer is explainable (rules surface plain-English reasons); `scorer_version` enables auditable re-scoring |
| ISO 42001:2023 (AI management) | Documented purposes (`docs/`), human-in-the-loop on BLOCK actions (officer reviews FRAUD disputes), audit emission on every model action |
| OWASP ASVS Level 2 | Input validation (Pydantic strict), rate limits, secrets in KMS, signed JWTs, audit logging |

## Right to erasure (Uganda DPA art. 26)

A citizen can request erasure of their personal data. We:

1. Delete the `nin_encrypted` blob; the queryable `nin_hash` remains but is
   one-way (no recovery).
2. Replace the `full_name` with the constant string `"[erased]"`.
3. Emit an `erasure_tombstone` event in the audit chain. The original chain
   rows stay intact (a Merkle proof must still verify), but downstream
   consumers MUST honour the tombstone when surfacing data.

This is the same pattern as the sibling URA Chatbot's GDPR work.

## Threat model

See [ARCHITECTURE.md § Threat model](./ARCHITECTURE.md#threat-model-abbreviated).
