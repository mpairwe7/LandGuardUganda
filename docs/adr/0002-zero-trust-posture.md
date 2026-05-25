# ADR-0002: Zero-Trust Posture for LandGuard Uganda

**Status:** Accepted, 2026-05-25.

## Context

LandGuard mediates **mutable claims about title to land** and **on-chain
custodial commitments**. The blast radius of a single compromised
component (officer laptop, RPC provider, container image, dependency) is
high enough that perimeter-trust models are unacceptable.

The 2026 NITA-U *Cybersecurity Posture for Critical National
Infrastructure* draft requires zero-trust architecture for any system
that mediates statutory records. We need to be explicit about which
zero-trust tenets we already meet, which we partially meet, and how the
gaps close on a pilot timeline.

## Decision

Adopt the **NIST SP 800-207** zero-trust tenets, plus three Uganda-
specific extensions, as the architectural reference. Each tenet maps to
either an implemented control, a configuration gate, or a documented
plan with a date.

### NIST SP 800-207 tenets

| # | Tenet | LandGuard implementation |
|---|---|---|
| 1 | All data sources and computing services are resources | Backend, frontend, chain RPC, NIRA, Redis are treated as discrete resources; each has its own circuit breaker / failure boundary |
| 2 | All communication is secured regardless of network location | TLS 1.3 everywhere (Caddy auto-TLS); inter-service comms over internal Docker network are nonetheless considered untrusted (no IP allowlists relied upon) |
| 3 | Access to individual enterprise resources is granted on a per-session basis | JWT 1-hour TTL; OIDC re-auth on expiry; idempotency keys scoped per user per route |
| 4 | Access is determined by dynamic policy | `require_role()` decorator computes authorisation at request time from JWT claims + role hierarchy |
| 5 | The enterprise monitors and measures integrity and security posture | Per-district hash chain (continuous integrity); Prometheus + OTel; chain verifier |
| 6 | All resource authentication and authorisation are dynamic and strictly enforced | Default-deny middleware chain; `optional_user → require_user → require_role` |
| 7 | The enterprise collects information about asset state and uses it to improve security | Audit chain *is* the security telemetry; `audit_failure_total` is alerted; CHANGELOG documents CVE response |

### LandGuard-specific extensions

1. **Cryptographic custody separation.** No single key can mutate
   immutable on-chain state: 3-of-5 multi-sig is the enforcement
   (`contracts/src/MultiSigRegistrar.sol`).
2. **Human-in-the-loop on custodial decisions.** No software path can
   freeze a parcel without a human-affirm audit row
   (`docs/AI_ETHICS_CHARTER.md` §1).
3. **Out-of-band escalation for highest-impact operations.** Smart-
   contract role rotation and right-to-erasure require written sign-off
   in addition to PR review (`MAINTAINERS.md`).

## Consequences

**Positive:**

- The system has a defensible answer to the NITA-U cybersecurity
  procurement question without retrofitting controls.
- The blast radius of any single compromise is bounded by the design,
  not by the configuration.
- An evaluator can verify each tenet from the codebase in minutes.

**Negative:**

- Operational complexity: every external dependency is wrapped in a
  circuit breaker, which means more configuration knobs. Mitigated by
  centralising the breaker in `backend/app/resilience.py`.
- JWT TTL of 1 hour forces re-auth more often than a session model
  would; an OIDC silent-refresh flow lands in the pilot scope.

## Alternatives considered

- **VPN-perimeter model.** Rejected because it gives a false sense of
  security and doesn't survive supply-chain compromise.
- **Service mesh (Istio / Linkerd) for mTLS everywhere.** Rejected at
  prototype scale (operational complexity for a single-host deployment);
  reconsidered at K8s rollout (year 2).
- **Step-up auth for high-impact endpoints (TOTP on title revocation,
  fraud affirmation).** Accepted as a pilot-scope addition; designed in
  but not yet implemented to keep the showcase demo path simple.
