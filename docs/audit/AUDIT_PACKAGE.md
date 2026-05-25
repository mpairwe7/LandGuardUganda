# Auditor's Package

A single-page index for technical reviewers (smart-contract auditors,
NITA-U security, MoLHUD ICT, civil-society observers, academic partners).

## In-scope artefacts

| Artefact | Path | What to look at |
|---|---|---|
| Anchor contract | `contracts/src/LandRegistryAnchor.sol` | AccessControl gating, Pausable kill switch, `verifyProof` sorted-pair keccak |
| Custody contract | `contracts/src/MultiSigRegistrar.sol` | 3-of-5 threshold, idempotent confirmations, `proposalIdOf` determinism |
| Contract tests | `contracts/test/*.t.sol` | Coverage targets ≥ 90% line + branch via `forge coverage` |
| Off-chain Merkle | `backend/app/audit/merkle.py` | Two regimes — SHA-256 (integrity) and sorted-pair keccak (on-chain anchor) |
| Audit ledger | `backend/app/audit/ledger.py` | Per-district hash chain, mutex-guarded append, erasure tombstones |
| Chain verifier | `backend/app/audit/verifier.py` | Rewalks the chain; reports first corrupt seq if integrity is broken |
| Anchor service | `backend/app/blockchain/anchor_service.py` | Volume + time triggers, circuit-breaker-wrapped commits |
| Fraud worker | `backend/app/fraud/worker.py` | Human-in-the-loop enforcement: no auto-FREEZE |
| Ethics charter | `docs/AI_ETHICS_CHARTER.md` | Governing policy for the scorer |
| Custody model | `docs/CUSTODY.md` | Five named signers, threshold, key custody plan |
| MOU template | `docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md` | Pilot agreement starting point |
| Threat model | `docs/audit/THREAT_MODEL.md` | Asset/threat/mitigation matrix |
| Codebase map | `docs/audit/CODEBASE_MAP.md` | File-by-file inventory of the current repo state |
| Changelog | `CHANGELOG.md` | Security + dependency timeline (CVE remediations) |

## Cryptographic invariants under test

1. **Chain integrity.** For any tenant, walking ``audit_events`` ordered by
   ``seq`` MUST reproduce the stored ``row_hash`` from
   ``sha256(prev_hash + payload_hash)`` with ``prev_hash`` seeded by
   ``GENESIS_HASH = "0"*64`` at seq=1.
   *Tested in*: ``backend/tests/test_audit_chain.py``.

2. **Cross-language Merkle agreement.** The Python ``compute_merkle_root_evm``,
   the TypeScript ``verifyMerkleProofEvm``, and the Solidity
   ``verifyProof`` MUST all accept the same (leaf, siblings, root) tuple
   over the published fixture in ``test_merkle_cross.py``.
   *Tested in*: ``backend/tests/test_merkle_cross.py``,
   ``contracts/test/LandRegistryAnchor.t.sol::test_VerifyProof_ThreeLeaves``.

3. **Multi-sig threshold.** ``LandRegistryAnchor.commitBatch`` is callable
   ONLY by the multisig once ``REGISTRAR_ROLE`` has been rotated; three
   distinct signers MUST confirm to execute.
   *Tested in*: ``contracts/test/MultiSigRegistrar.t.sol``.

4. **Human-in-the-loop.** A ``BLOCK`` score persists to ``fraud_review_queue``
   but MUST NOT change any parcel's status. The parcel goes to ``FROZEN``
   only on ``FRAUD_HUMAN_AFFIRMED`` or ``FRAUD_AUTO_ESCALATED``.
   *Tested in*: ``backend/tests/test_fraud_review_workflow.py``.

5. **Idempotency.** Submitting the same mutating endpoint twice with the
   same ``Idempotency-Key`` MUST return the cached response, not re-execute.
   *Implementation*: ``backend/app/middleware/idempotency.py``. A
   dedicated ``test_idempotency.py`` is on the open-tracker; the property
   is exercised indirectly by ``test_anchor_service.py`` and
   ``test_verify_endpoint.py`` today.

## How to reproduce a verification from scratch

```bash
# 1. Build contracts and run their tests (Foundry)
cd contracts && forge build && forge test -vvv

# 2. Bring up the stack including multisig + co-signer
MULTISIG_ENABLED=true docker compose --profile default --profile multisig up -d --build

# 3. Seed + issue a title
docker compose exec backend python scripts/seed_districts.py
docker compose exec backend python scripts/seed_demo.py
docker compose exec backend python scripts/train_fraud_model.py

# 4. Run the backend test suite (forces a 3-of-5 anchor)
docker compose exec backend uv run pytest -q

# 5. Verify the chain
docker compose exec backend python scripts/verify_audit_chain.py 3

# 6. Cross-language Merkle vector check
docker compose exec backend uv run pytest tests/test_merkle_cross.py -v

# 7. Demographic parity audit (run once you have transfers)
docker compose exec backend python scripts/fraud_parity_audit.py

# 8. Force an anchor and read the proof from the public verifier
curl -X POST http://localhost:8000/api/v1/anchors/flush/3
curl -X POST http://localhost:8000/api/v1/verify/title \
     -H 'content-type: application/json' \
     -d '{"title_no":"UG-MIT-T00001/2026"}'
```

## Trust assumptions

- The auditor trusts the SHA-256 + Keccak-256 primitives.
- The auditor does NOT need to trust LandGuard's source code: the on-chain
  ``verifyProof`` and the off-chain ``verify_merkle_proof_evm`` are
  byte-identical algorithms; if they disagree on a proof the system is
  broken and observable.
- The auditor does NOT need to trust the operator's database: ``audit
  chain verifier`` and ``fraud parity audit`` produce reports rooted in
  the on-chain anchor, not in operator-supplied summaries.

## Contact

For audit-coordination matters: `kalemaaaaaaaa@gmail.com`. We welcome
findings, redaction requests, and follow-up access to a sandbox deployment.
