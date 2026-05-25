# ADR-0003: Regional / EAC Chain Migration Path

**Status:** Accepted, 2026-05-25.

## Context

LandGuard's prototype runs on local Anvil for development and Sepolia
for testnet. Mainnet posture is intentionally **unfrozen** in the
prototype so the operator (MoLHUD via NITA-U) chooses the production
chain. There are three live candidates as of 2026:

1. **A Ugandan government-permissioned chain** (Bank of Uganda is
   piloting Hyperledger Besu for digital-currency settlement; could
   accommodate land anchors).
2. **An EAC regional permissioned chain** (proposed under the EAC
   e-Government Strategy 2027).
3. **A public EVM L2** (e.g. Polygon PoS, Arbitrum One) for the
   prototype-to-pilot bridge while the permissioned options mature.

Picking the **wrong** chain locks in custodial assumptions for years.
Picking **all three at once** invites integration cost. We need a
default plus an upgrade path.

## Decision

Adopt this sequence:

```
Showcase (2026-06-25)  →  Anvil + Sepolia (testnet posture)
Pilot Y1 (2026 Q3+)    →  Polygon PoS mainnet  (default)
Pilot Y2 (2027)        →  EAC regional chain   (if commissioned)
Pilot Y2+ (2027+)      →  Bank of Uganda permissioned  (if available)
```

The migration mechanism is **a single environment variable change**
plus an address-file update. The `BlockchainClient` Protocol in
`backend/app/blockchain/client.py` is the abstraction; existing
implementations (`anvil_client.py`, `sepolia_client.py`) prove the
shape.

### What does NOT migrate

- Off-chain audit ledger (unchanged; chain-agnostic).
- Smart-contract source (`LandRegistryAnchor.sol`,
  `MultiSigRegistrar.sol` are vanilla Solidity, no chain-specific opcodes).
- Public verifier UX (always shows the active chain's chain_id; UI
  copy adapts automatically).

### What DOES migrate

| Concern | Action |
|---|---|
| Custodial keys | Issued fresh on the new chain (HSM-protected, signing ceremony recorded in `docs/CUSTODY.md`) |
| Contract addresses | Pinned in `data_store/contract_address.json` per chain; the file already supports `{address, sepolia, multisig_address, chain_id}` keys |
| Gas strategy | Subclass `BlockchainClient`; the Sepolia variant already demonstrates EIP-1559 fee strategy distinct from Anvil legacy gas |
| Anchors made on previous chains | Remain forever verifiable on those chains — printed QR codes embed the chain_id |

### Bridging old + new chains during a transition window

For an MN-quarter overlap window, run **both** chains active:

- `BlockchainClient` becomes a multiplexer: writes go to the new chain;
  reads check both. The off-chain audit ledger holds the canonical
  truth; old chain reads are a courtesy.
- Once the operator declares cutover complete, the multiplexer is
  retired; the old chain stops receiving writes but reads continue
  against an archive node.

## Consequences

**Positive:**

- **Optionality** for the government operator: choose the chain that
  matches sovereignty preference and procurement reality at pilot Y2,
  not at submission day.
- **Vendor-agnostic** by construction: any EVM-compatible chain works.
- **Forward-secure**: anchors made on the old chain remain verifiable
  forever; only future commits move.

**Negative:**

- Multi-chain operations during the bridging window add operational
  load. Mitigated by limiting the window to a single quarter and
  pre-publishing the cutover date.
- Adds a `chain_id` discriminator to the public verifier's UX — handled
  with the existing `chain_id` field already in `AnchorReceipt`.

## Alternatives considered

- **Commit to Polygon mainnet permanently.** Rejected: defeats the
  sovereignty narrative central to government adoption.
- **Permissioned chain from day one.** Rejected: pilot needs to ship
  with a live, observable chain; permissioned options aren't ready.
- **No public chain — only off-chain ledger + an externally-published
  daily Merkle digest.** Rejected: weakens the tamper-evidence claim
  to "trust the operator's blog".

## Verification

The Sepolia migration path is the canonical proof:

```bash
docker compose -f docker-compose.yml -f docker-compose.sepolia.yml up -d --build
```

Two env vars + a deploy + a pinned address — the entire migration
surface. The same pattern applies for every future chain.
