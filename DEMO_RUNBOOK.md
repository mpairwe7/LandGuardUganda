# DEMO_RUNBOOK — 25 June 2026 MoICT&NG Showcase

A tight 8–12 minute storyboard for the **Uganda MoICT&NG National Innovator
Registry** evaluation. Calibrated for technical-but-non-engineer evaluators
and explicitly engineered around the seven evaluation criteria.

## Day-of checklist (15 minutes before stage)

- [ ] **Multi-sig mode** `MULTISIG_ENABLED=true docker compose --profile default --profile multisig up -d --build`
- [ ] Confirm all services healthy: `docker compose ps`
- [ ] Confirm co-signer daemon up: `docker compose logs co-signer | tail`
- [ ] `python scripts/seed_districts.py && python scripts/seed_demo.py && python scripts/train_fraud_model.py`
- [ ] Sanity-check at **<http://localhost:3000>** — public landing shows a recent anchor badge
- [ ] Pre-anchor 3 batches from the morning of (flush 3× with 30s pauses) so the timeline isn't empty
- [ ] Print **20× two-page A5 handouts** on 200 gsm with the verification QR + USSD code
- [ ] Mi-Fi from second carrier · charged · paired with laptop
- [ ] **Three test phones**: iPhone (Safari), Android (Chrome), and a **Tecno feature phone** with prepaid airtime for USSD
- [ ] Pre-installed PWA on the demo smartphone for offline-verifier fallback
- [ ] Backup recording of the demo on the laptop (`bun run scripts/record_dress_rehearsal.sh`)
- [ ] Print the MOU template (`docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md`) on letterhead

## The script

### HOOK · 0:00 – 1:00

> "Good morning. I'd like you to take out your phones — and one of you,
>  please come to the front; I'll hand you a feature phone. You're about to
>  verify a Ugandan land title against a public blockchain, on your own
>  device — whether that's a smartphone or a feature phone. Nobody is
>  excluded."

**On screen:** Full-screen QR at <http://localhost:3000/verify?title=UG-MIT-T00007/2026>.
Below it, the USSD code: **`*247*256#`** → `1` → `UG-MIT-T00007/2026`.

**Tech:** PWA verifier (smartphones) + Africa's Talking USSD (feature phones).

**Failure mode:** Mi-Fi backup. Printed handout has a printed verification
hash that evaluators can type into the offline PWA after the cache loads.

---

### ACT 1 · The problem · 1:00 – 2:00

> "Meet Mrs. Sarah Nakato — a smallholder coffee farmer in Mityana. Last
>  year she discovered three other people held titles to her family's
>  land. UN-Habitat estimates 60 percent of Uganda's land is unclear or
>  contested. NLIS records this; LandGuard makes the records
>  arithmetically impossible to alter without detection."

**On screen:** Citizen portal as Mrs. Nakato. Three "ghost" titles
overlapping on a Mityana map.

**Failure mode:** Pre-rendered screenshots at `?demo=1&fallback=act1`.

---

### ACT 2 · Anchoring with 3-of-5 custody · 2:00 – 4:30

> "Mr. Otim, the District Surveyor, registers a new parcel. The District
>  Registrar issues the title. Watch what happens — and watch carefully,
>  because no single key can anchor this. We have **five named signers
>  and need three of them to agree**: MoLHUD, NITA-U, the District Land
>  Board, our backend, and an independent observer."

**On screen sequence:**

1. <http://localhost:3000/surveyor/register> — draw polygon (real-time Turf overlap).
2. Switch role → REGISTRAR. <http://localhost:3000/registrar> — click Issue.
3. `MerkleProofVisualizer` animates: leaf → siblings → root.
4. Split-screen: terminal showing co-signer daemon logging "MoLHUD confirmed",
   "NITA-U confirmed" — three transactions within ~3 seconds.
5. The anchor lands on Anvil; tx hash appears.

**Tech:** Real `MultiSigRegistrar.proposeAndConfirm` traversal — three
distinct on-chain transactions before `LandRegistryAnchor.commitBatch`
fires. The on-chain log shows separate `ProposalCreated`,
`ProposalConfirmed`, `ProposalExecuted` events.

**Failure mode:** If the co-signer daemon doesn't fire, presenter manually
runs `python scripts/co_sign_daemon.py` in a side terminal. If the chain
itself is slow, pivot to Act 5 ("And this is exactly the resilience
moment…").

---

### ACT 3 · AI flags, humans decide · 4:30 – 6:30

> "Now I'll attempt fraud. I'm Patrick Bwambale, a fictional broker, trying
>  to transfer Mrs. Nakato's title using a forged NIN. The AI flags it
>  immediately — but pay attention: **the AI does not freeze the parcel.**
>  A Land Officer must affirm. That's the ethical floor: no custodial
>  decision is made by software alone."

**On screen sequence:**

1. Switch role → LAND_OFFICER trying to initiate transfer with fraudulent NIN.
2. Fraud worker fires in ~1s; three signals visible in `FraudExplainer`:
   - **KYC unverified at NIRA** (`CM82010110A4P9` returns no match).
   - **Fraud watchlist match** — 97% to "Patrick Bwambale".
   - **Rapid retransfer** if the parcel has prior transfers from earlier demo runs.
3. Open <http://localhost:3000/officer> — review queue shows the BLOCK alert
   in **PENDING_REVIEW** state.
4. The parcel is still **ACTIVE** — emphasise this. Open the parcel page in
   a second tab to confirm.
5. Officer types notes ("Confirmed forgery — buyer ID does not match NIRA
   photo") and clicks **Affirm — freeze parcel**.
6. NOW the parcel is FROZEN; the FRAUD dispute auto-files; the audit chain
   records `FRAUD_HUMAN_AFFIRMED` with the officer's user_id.

> "If the officer had been bribed or had simply missed the alert, the
>  citizen has an appeal pathway. Citizens can never be silenced by
>  software. And we run a quarterly demographic-parity audit so the
>  scorer itself is auditable for bias."

**Tech:** `app/fraud/worker.py` writes to `fraud_review_queue`;
`app/routers/fraud.py:affirm_review` is the only path to FROZEN.

**Failure mode:** Rules-only fallback (model file missing) still fires the
three signals — they're rule-based.

---

### ACT 4 · The audience verifies (smartphone + feature phone) · 6:30 – 8:30

> "Now please raise your phones again. Scan the new QR. The feature phone
>  user, dial *247*256# and enter the new title number. You are
>  verifying the title we just issued, against the blockchain, with no
>  involvement from me or my server."

**On screen:** Fresh QR for the new title + USSD code. Stage business:
presenter dramatically closes the laptop lid for two seconds.

**Tech:** Smartphone PWA verifies against the on-chain root; feature phone
USSD verifies via Africa's Talking; both paths converge on
`LandRegistryAnchor.verifyProof`. The audit chain records both
verifications.

**Failure mode:** Venue Wi-Fi failure — Mi-Fi second carrier. Handout has
a printed proof hash for manual comparison.

---

### ACT 5 · Resilience · 8:30 – 10:30

> "Let me break something on purpose. I'm killing the blockchain. Watch —
>  titles still issue. Anchors queue. Now I restore — and watch the queue
>  drain. The off-chain hash chain never blocks on the on-chain anchor."

**On screen sequence:**

1. Open <http://localhost:3000/demo?demo=1>.
2. Press **Kill RPC**. `ChainStatusBeacon` turns amber.
3. Switch to <http://localhost:3000/registrar>, issue another title — works.
   `PendingAnchorBadge` is amber.
4. Press **Restore RPC**. Press **Flush Mityana now**.
5. The pending badge flips to green; the new tx appears on the anchor explorer.

**Failure mode:** Physically unplug Ethernet if the kill endpoint hangs.

---

### CLOSE · 10:30 – 12:00

> "LandGuard Uganda is a working prototype that proves five things: that
>  records are tamper-evident; that anchoring costs pennies per batch;
>  that no foreign or single operator controls custody; that AI assists
>  humans, never replaces them; and that even a citizen with a feature
>  phone can verify their own land. We have a draft MOU ready for Mityana,
>  signers identified for MoLHUD and NITA-U, and an invitation to Makerere
>  CSL as the independent observer. We're asking MoICT and NG to admit
>  LandGuard to the National Innovator Registry."

**On screen:** Single CTA slide with the MOU template URL, the GitHub repo,
and `mpairwelauben75@gmail.com`. Hand the printed MOU draft to the senior
evaluator if appropriate.

## What MUST work flawlessly

1. **QR + USSD at minute 1.** Pre-tested on three phone models including a Tecno.
2. **Multi-sig anchor at minute 3.** Three distinct on-chain transactions in
   the co-signer terminal.
3. **The "affirm" click at minute 6.** This is the ethical-AI argument —
   if it fails the entire human-in-the-loop story falls apart.
4. **MerkleProofVisualizer animation.** Smooth motion; rehearsed.
5. **RPC-kill at minute 9.** Proves the resilience argument.

## What NOT to demo

- Auditor "chain verify" if it takes >3 seconds (use a screenshot in slides).
- Mobile-phone surveyor drawing (too fiddly under stage lights).
- Admin user-management screens (boring).
- The raw FastAPI OpenAPI docs (looks unfinished).
- The `fraud_parity_audit.py` raw output (show a slide instead).

## Seed data crib sheet

- Hero parcel: `UG-MIT-024718/2026` — owned by **Sarah Nakato** (NIN `CM82010110A4P0`).
- Fraudster: **Patrick Bwambale** (NIN forgery `CM82010110A4P9`, watchlist-flagged).
- Hero title issued during the demo: `UG-MIT-T00007/2026`.
- Other citizens: Joseph Okello (Gulu), Aisha Namatovu (Wakiso), Esther Auma (Kampala).
- Demo roles: `demo-citizen`, `demo-surveyor`, `demo-officer`, `demo-registrar`, `demo-auditor`, `demo-admin`.
- USSD shortcode (showcase placeholder): `*247*256#`.

## Mapping demo acts → evaluation criteria

| Act | Primary criterion shown |
|---|---|
| HOOK | Usability, Local Innovation Value |
| Act 1 | Relevance to Government Needs |
| Act 2 | Technical Soundness, Security & Compliance |
| Act 3 | Security & Compliance, **Ethics of AI** |
| Act 4 | Usability (inclusion via USSD), Local Innovation Value |
| Act 5 | Scalability, Technical Soundness |
| CLOSE | Innovator Capability |

## Connectivity backup plan

1. **Tier 1:** Mi-Fi from a second carrier.
2. **Tier 2:** Demo Control Panel switches the backend to local Anvil —
   PWA verifies against whichever chain ID the proof references; USSD path
   is unaffected (it's a backend round-trip, not a chain round-trip).
3. **Tier 3:** Pre-recorded 90s screencast embedded at `/page.tsx?demo=video`,
   framed as "pilot test footage from last week".
