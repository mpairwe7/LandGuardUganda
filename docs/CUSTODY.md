# Custody Model — Who Can Anchor a Batch

A land registry is only as trustworthy as the keys that sign it. LandGuard
moves on-chain custody from a **single private key** (the obvious attack
surface) to a **3-of-5 named threshold signature** through the
`MultiSigRegistrar` contract.

## The five named signers

| # | Role | Held by | Hardware |
|---|---|---|---|
| 1 | Commissioner Land Registration | Ministry of Lands, Housing & Urban Development (MoLHUD) | HSM in MoLHUD ICT centre |
| 2 | Security Lead | National Information Technology Authority (NITA-U) | HSM in NITA-U TIER III data centre |
| 3 | District Land Board chair | Rotating district (Mityana for pilot) | Hardware wallet + biometric approval |
| 4 | LandGuard backend signer | LandGuard pilot team | Cloud KMS (separated from app servers) |
| 5 | Independent auditor | Civil-society / academic observer (e.g. Makerere CSL) | Hardware wallet, offline by default |

Threshold: **3 of 5 must sign every anchor batch**.

No single party can anchor on their own. Two compromised parties together
cannot anchor. Three compromised parties — including either MoLHUD or
NITA-U — is the trust floor.

## Why threshold signatures, not multi-sig wallet ownership

Gnosis Safe and similar multisig wallets are excellent — and we'd use one in
production. For the prototype we ship a **bespoke 80-line contract**
(`contracts/src/MultiSigRegistrar.sol`) for three reasons:

1. **Auditability.** Every confirmation emits its own event; auditors can
   reconstruct who confirmed what without scanning a generic Safe transaction
   trace. The contract is small enough to read in one sitting.
2. **Zero dependencies.** Adding Safe contracts in a Ugandan permissioned
   chain may require coordination we don't yet have.
3. **Migration optionality.** When a Safe-of-record is operational, the
   `MultiSigRegistrar` can be retired by transferring `REGISTRAR_ROLE` from
   it to the Safe — no contract change in `LandRegistryAnchor`.

## What the on-chain flow looks like

```
LandGuard backend → MultiSigRegistrar.proposeAndConfirm(batchId, root)
                     │
                     ├── emits ProposalCreated  (confirmations = 1)
                     │
MoLHUD HSM signer  → MultiSigRegistrar.proposeAndConfirm(same batchId, root)
                     │
                     ├── emits ProposalConfirmed  (confirmations = 2)
                     │
NITA-U HSM signer  → MultiSigRegistrar.proposeAndConfirm(same batchId, root)
                     │
                     ├── emits ProposalConfirmed  (confirmations = 3)
                     ├── threshold met → calls LandRegistryAnchor.commitBatch
                     └── emits ProposalExecuted
```

Confirmations are idempotent per signer; replayed proposals add nothing.
A proposal whose `(districtId, batchId, merkleRoot)` triplet does not match
the original is treated as a new proposal — the proposalId is deterministic
on those three fields. This means rogue parameter swaps are silently
isolated, not silently merged.

## Demo mode

For the showcase you can either:

- **Run single-signer custody (default):** `MULTISIG_ENABLED=false`. Fast,
  simple, demonstrates the cryptographic chain without the multi-party
  coordination overhead.
- **Run multi-sig with the auto co-signer daemon:**
  ```bash
  MULTISIG_ENABLED=true docker compose --profile default --profile multisig up -d
  ```
  The `co-signer` service holds Anvil accounts 1 and 2 (MoLHUD + NITA-U
  personas) and auto-confirms within ~2s. Every anchor in the live demo
  visibly traverses the three-confirmation path; the auditor console
  surfaces the `ProposalCreated` → `ProposalConfirmed` → `ProposalExecuted`
  trail.

For the **25 June showcase**, we recommend running `MULTISIG_ENABLED=true`
in a final Act-5 "production mode" segment to demonstrate the custody story
explicitly. The visual is impressive: three named keys, three separate
transactions, one anchor.

## Production posture checklist

- [ ] Hardware security modules procured for MoLHUD and NITA-U signers
- [ ] Signing ceremony documented with role-separation requirements
- [ ] Quarterly key rotation cadence agreed in the steering charter
- [ ] Independent auditor confirmed (Makerere CSL written commitment)
- [ ] Incident-response playbook covers ≤2 simultaneous key compromises
- [ ] Smart-contract third-party review complete (recommend Makerere CSL or
      a regional firm; budget ~UGX 5M for an 8-hour engagement)
- [ ] Emergency pause path tested: the existing `pause()` on
      `LandRegistryAnchor` can be invoked by `DEFAULT_ADMIN_ROLE` to halt
      all new commits if a smart-contract bug is found
