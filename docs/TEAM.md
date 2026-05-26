# Team & Capacity

**Honesty disclaimer:** LandGuard Uganda is presented at the showcase as a
**working prototype with a credible coalition of intended partners**, not
as a deployed system staffed by a 30-person team. Where institutional
roles are listed as *designate*, they are not yet contractually filled
and are documented as such — both here and in
`docs/AI_ETHICS_CHARTER.md` §9. This is by design: pretending we have
signed institutional partners we don't have would be the fastest way to
lose panel credibility.

---

## 1. Project lead

| Field | Value |
|---|---|
| Name | Kalema (project lead) |
| GitHub | <https://github.com/mpairwe7> |
| Email | `mpairwelauben75@gmail.com` |
| Role | Architecture, implementation, demo |
| Verifiable artefacts | All commits in <https://github.com/mpairwe7/LandGuardUganda> are signed by this email; `git shortlog -sne` matches |

---

## 2. Pilot coalition (designate signers)

The 3-of-5 custody model in `docs/CUSTODY.md` names five institutional
signers. None has signed the pilot MOU yet (the MOU template in
`docs/moa-templates/` is the negotiation basis). Disclosure of intent:

| # | Role | Intended institution | Status | Engagement plan |
|---|---|---|---|---|
| 1 | Commissioner Land Registration | MoLHUD | Designate — no MOU signed | Pilot-MOU outreach via MoICT&NG following showcase |
| 2 | Security Lead | NITA-U | Designate — no MOU signed | NITA-U cybersecurity desk briefing scheduled post-showcase |
| 3 | District Land Board chair | Mityana DLB | Designate — Mityana selected on overlap-density and pilot-readiness grounds | Direct outreach via Mityana District ICT Officer |
| 4 | LandGuard project signer | LandGuard team | Held by project lead in the prototype; HSM-protected at pilot launch | This repo |
| 5 | Independent observer | Makerere CSL (preferred) | Conversation pending; alternatives: CIPESA, ICT4D Lab | Engagement letter drafted, attached to showcase package |

This composition is consistent with the Uganda Innovation Coalition
guidance (MoICT&NG 2025) of ≥ 1 ministry, ≥ 1 statutory regulator,
≥ 1 sub-national authority, and ≥ 1 independent observer per
prototype-stage digital public infrastructure project.

---

## 3. Governance model

```
┌────────────────────────────────────────────────────────────┐
│ Steering Committee (quarterly)                             │
│ ─────────────────                                          │
│ MoLHUD designate · NITA-U designate · MoICT&NG observer    │
│ Independent observer · LandGuard project lead              │
│ Charter: docs/AI_ETHICS_CHARTER.md §1                      │
└──────────────────────────┬─────────────────────────────────┘
                           │ Sets policy, reviews parity audits,
                           │ approves model-card go-lives.
                           ▼
┌────────────────────────────────────────────────────────────┐
│ Technical Maintainers                                      │
│ ─────────────────                                          │
│ Decisions: ADR-recorded, public, reversible by a follow-up │
│ ADR. Threshold: 2-of-3 reviewers on security-impacting     │
│ PRs (see MAINTAINERS.md).                                  │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│ Contributors (Apache-2.0, public PR review)                │
└────────────────────────────────────────────────────────────┘
```

---

## 4. ADR (Architecture Decision Record) discipline

We make architecturally-binding decisions explicitly in `docs/adr/`. The
process is intentionally lightweight:

1. Draft an ADR with **Context · Decision · Consequences · Alternatives
   considered**. Use the next sequential number.
2. PR for review; merge when 2 maintainers approve.
3. ADRs are immutable after merge — a superseding ADR re-opens the
   question. See ADR-0001 for the canonical example.

Active ADRs:

- ADR-0001 — Dual-Merkle hashing regime (accepted 2026-05-21)
- ADR-0002 — Zero-trust posture (accepted 2026-05-25)
- ADR-0003 — Regional / EAC chain migration path (accepted 2026-05-25)

---

## 5. Capacity-building commitments

The single biggest sustainability risk for a Uganda-led digital-public-
infrastructure project is **one-person dependency**. We mitigate it
with the following, on a pilot timeline:

| Commitment | Partner | Window | Status |
|---|---|---|---|
| 4-week immersive engineering apprenticeship for 2 Makerere CSL final-year students | Makerere CSL | Q3 2026 (post-showcase) | Letter of intent drafted |
| Open Saturday workshop in Mityana District ICT Hub teaching the audit chain + Merkle verifier in pure Python | Mityana DLB + local hub | Q4 2026 | Schedule with DLB pending pilot MOU |
| Public Lunch-and-Learn for civil-society reviewers (CIPESA, HURIPEC) on AI ethics charter + appeals pathway | CIPESA, HURIPEC | Q4 2026 | Scope outlined |
| Land-Information curriculum module contribution to Makerere CSL undergraduate course | Makerere CSL | Q1 2027 | Course-lead conversation pending |
| Annual independent security review (smart contracts + backend) | Makerere CSL or regional firm | 2027-onwards, annually | Budgeted UGX 5M / year (see `README.md` Roadmap) |

These are commitments, not aspirations. The Steering Committee receives
quarterly capacity-building status updates as a standing agenda item.

---

## 6. Hiring posture (post-pilot)

If the pilot succeeds and MoLHUD adopts LandGuard for national rollout,
target team composition (steady-state, year 2):

| Role | Headcount | Sourcing preference |
|---|---:|---|
| Backend / SRE engineers (Python, FastAPI, Postgres) | 3 | Ugandan; ≥ 1 woman |
| Frontend engineers (React, accessibility specialist) | 2 | Ugandan |
| Smart-contract engineer (Solidity, Foundry) | 1 | EAC region |
| AI/ML engineer (explainability + parity audits) | 1 | EAC region |
| Compliance & DPO | 1 | Ugandan, advocate qualification preferred |
| Field-coordinator (district relations, USSD user research) | 1 | Mityana resident preferred |
| Engineering manager | 1 | Ugandan; ≥ 5 years platform leadership |

Hiring is conditional on pilot MOU; this section is documentation of
**intent**, not commitments.

---

## 7. Code of Conduct

The repository adopts the [Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
Enforcement contact: `mpairwelauben75@gmail.com`. A separate
`CODE_OF_CONDUCT.md` lives at the repo root.

---

## 8. Verifiable claims (no hand-waving)

| Claim | How a panellist verifies it in 60 seconds |
|---|---|
| "Single sustained author so far" | `git shortlog -sne` |
| "ADR discipline" | `ls docs/adr/` — three ADRs, sequentially numbered, dated |
| "Open-source under Apache-2.0" | `LICENSE` file at repo root; no source-available restrictions |
| "Documentation discipline" | `find docs -name '*.md' | wc -l` — 14+ documents, all dated |
| "CVE-responsiveness" | `CHANGELOG.md` shows two CVE-driven bumps within 24 hours of Dependabot alerts |
| "Reproducible from scratch" | `docs/audit/AUDIT_PACKAGE.md` §"How to reproduce" — eight bash commands |
