# Maintainers

The maintainers list governs **review authority** on this repository.
A change to a file in any of the paths below requires the listed
review threshold before merge.

## Current maintainers

| Handle | Areas of responsibility | Contact |
|---|---|---|
| `@mpairwe7` | All (sole maintainer for the prototype phase) | `mpairwelauben75@gmail.com` |

When the pilot starts (post-25 June 2026), at least two additional
maintainers will be added under the rules in `docs/TEAM.md` §6.

## Review thresholds by area

| Path | Threshold | Why |
|---|---:|---|
| `contracts/src/**` | 2 of 2 maintainers + 1 external smart-contract reviewer | Smart-contract changes alter immutable on-chain state |
| `backend/app/audit/**`, `backend/app/blockchain/**` | 2 of 2 maintainers | Touches the cryptographic and custodial path |
| `backend/app/fraud/**`, `backend/app/auth/**` | 2 of 2 maintainers | AI ethics and authn impact |
| `backend/app/db/migrations/**` | 2 of 2 maintainers | Schema changes are forward-only |
| `docs/audit/**`, `docs/adr/**`, `docs/AI_ETHICS_CHARTER.md`, `docs/CUSTODY.md` | 1 maintainer + 1 governance reviewer | Public commitments to evaluators |
| Everything else | 1 maintainer | Standard PR review |

**Prototype-phase note:** With one sole maintainer, the "2 of 2" rule
collapses to "1 maintainer + 1 invited external reviewer" for any
security-impacting change. External reviewer rotation is recorded in
the PR description; recent reviewers logged in
`docs/TEAM.md` §5 (capacity-building) and the GitHub PR history.

## Out-of-band review escalation

For changes touching the on-chain `REGISTRAR_ROLE` rotation, smart-
contract upgrades, or right-to-erasure (DPPA §26) flows, **a written
go-live note** signed by the project lead and one Steering Committee
designate is required in addition to PR review. See
`docs/AI_ETHICS_CHARTER.md` §7 for the analogous model-card process.

## Becoming a maintainer

The path is intentionally short and merit-based:

1. Sustained contributions over ≥ 3 months in your declared area.
2. ≥ 5 reviewed PRs in that area without dispute escalations.
3. Sponsorship by an existing maintainer at the next Steering
   Committee meeting (quarterly).

## Security reports

**Do not open public issues for security vulnerabilities.** Send a
signed email to `mpairwelauben75@gmail.com`. The recipient PGP key
will live at
[`docs/security/landguard-maintainer.asc`](./docs/security/landguard-maintainer.asc)
once the maintainer completes the keygen ceremony documented in
[`docs/security/KEYGEN_CEREMONY.md`](./docs/security/KEYGEN_CEREMONY.md);
the fingerprint will replace this line on or before **2026-06-01** and
will be cross-posted on the maintainer's GitHub profile so a forged
in-repo key is detectable out-of-band.

**Until the ceremony lands**, please send vulnerability reports with
encrypted attachments to the same address using **age**
([age-encryption.org](https://age-encryption.org)) against the
maintainer's GitHub SSH keys (already published and verifiable at
`https://github.com/mpairwe7.keys`) as a fallback.

We target ≤ 72-hour acknowledgement and a coordinated-disclosure
window of ≤ 90 days for high-severity findings.
