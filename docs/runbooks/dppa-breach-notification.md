# DPPA-2019 §19 Breach-Notification Runbook

**Last reviewed:** 2026-05-25.
**Owner:** LandGuard DPO (jointly held with MoLHUD per pilot MOU).
**Activated by:** Sev-1 / Sev-2 incident under `docs/SLA_TARGETS.md` §6.

The Uganda Data Protection and Privacy Act 2019 §19 requires the data
controller to notify the Personal Data Protection Office (PDPO) and
affected data subjects **within 72 hours** of becoming aware of a breach
likely to result in a risk to the rights and freedoms of natural
persons.

This runbook is the dated, audit-traceable procedure. It is referenced
in `docs/SLA_TARGETS.md` §7 and the breach-notification posture row of
`docs/GOVERNANCE.md`.

---

## 1. Trigger criteria — what counts as a "breach"

A breach occurs when any of the following holds:

1. **Confidentiality:** unauthorised disclosure of, or access to, PII
   the system holds (`owners.nin_encrypted`, `owners.full_name`, raw
   phone numbers, biometric templates).
2. **Integrity:** unauthorised alteration of an immutable record (audit
   ledger row, smart-contract anchor, on-chain custody).
3. **Availability:** unauthorised destruction or loss of access to PII
   or to a record that a data subject is statutorily entitled to view.

The DPO MUST treat the following as **automatic-yes triggers** without
case-by-case judgement:

- Audit-chain verifier reports `verified=False` for any district
  (`scripts/verify_audit_chain.py`).
- `audit_failure_total{...}` Prometheus counter increments outside a
  controlled migration window.
- Multi-sig key compromise reported or suspected (any of the five
  signers).
- A PR or commit lands that touches `owners.nin_encrypted`,
  `audit_events`, or the `crypto.py` keys without a DPO label.

---

## 2. The 72-hour clock

The clock starts when the LandGuard team **becomes aware** of the
breach, not when it occurred. "Becomes aware" means a member of the
maintainer list (`MAINTAINERS.md`) has read evidence sufficient to
conclude the breach is more likely than not.

| Hour | Required action | Owner |
|---|---|---|
| 0 | Triage call opened; primary on-call notified | Primary on-call |
| 0–1 | Confirm scope: which `nin_hash` values affected, which districts, which roles, which timeframe | Primary on-call + DPO |
| 1–4 | Containment: rotate keys / pause anchors / revoke staff roles as needed; preserve forensic evidence | Maintainers + MoLHUD designate |
| 4–24 | Drafted notification letter to PDPO (template in §6) ready for DPO sign-off | DPO |
| 24–48 | Notification letter sent to PDPO; data-subject SMS notification queued | DPO |
| 48–72 | Public statement on `https://landguard.ug/status` + audit chain `BREACH_NOTIFIED` event emitted | DPO + project lead |
| 7 days post | Post-mortem published (public version) | Maintainers |

If any step slips, the slip itself is logged as a separate Sev-2 and
the post-mortem must address it.

---

## 3. Decision tree

```
                       Incident detected
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         PII exposed?   Chain tampered?   Key compromised?
              │               │               │
              └───────┬───────┘               │
                      ▼                       │
              Activate this runbook  ←────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   Affects 1+    Affects no     Borderline →
   data subjects PII at all     escalate to DPO
        │             │
        ▼             ▼
   72-h clock    No DPPA §19
   starts        notification
                 (still post-mortem)
```

Borderline cases — when in doubt, **notify**. The DPPA penalty for
late notification is materially worse than the reputational cost of
proactive notification.

---

## 4. Roles & responsibilities

| Role | Responsibility |
|---|---|
| Primary on-call | Detects, opens incident, confirms scope, kicks off containment |
| DPO | Owns the 72-hour clock; drafts and sends PDPO notification; coordinates with MoLHUD legal |
| Project lead | Authorises public statement; signs off on key rotation; final approver of post-mortem |
| MoLHUD designate | Co-signs PDPO notification; coordinates with NIRA if NIN data is affected |
| NITA-U designate | Provides forensic support; co-signs if NITA-U infrastructure (Crane Cloud Tier-III host) is involved |
| Independent observer | Reviews the post-mortem; can publish a dissenting addendum |

A single individual MUST NOT hold both "DPO" and "incident
responder" roles for the same incident — this is the separation-of-
duties safeguard against under-notification.

---

## 5. Containment-specific procedures

### 5.1 PII exposure (e.g. database read leaked)

1. Revoke the database role / API token used in the attack.
2. Identify the `nin_hash` set affected via audit-chain replay:
   ```sql
   SELECT DISTINCT payload_json::jsonb->>'nin_hash'
     FROM audit_events
    WHERE ts > <attack_start_ts>
      AND event_type LIKE 'OWNER%';
   ```
3. Cross-reference to `owners.id` to identify data subjects to notify.
4. Rotate `PII_ENCRYPTION_KEY` (see `MAINTAINERS.md` "Out-of-band
   review escalation").

### 5.2 Audit-chain tampering

1. Identify the first corrupt `seq` via
   `python scripts/verify_audit_chain.py <district_id>`.
2. Compare the suspect rows' `row_hash` to the **anchored** Merkle root
   on chain — the chain is immutable, so any divergence is observable.
3. Pause anchor commits via `LandRegistryAnchor.pause()` under
   `DEFAULT_ADMIN_ROLE`. Document who invoked the pause and when in
   `docs/incidents/chain-pause-YYYY-MM-DD.md`.
4. Reconstruct the correct chain by replaying audit emissions from
   surviving backups; do **not** edit the existing ledger rows.

### 5.3 Multi-sig key compromise

1. Convene the Steering Committee (`docs/AI_ETHICS_CHARTER.md` §1)
   immediately — within hours, not days.
2. Identify which of the five signers is compromised.
3. Confirm the remaining ≥ 3 signers are uncompromised (out-of-band
   verification — phone calls, not chat).
4. Deploy a fresh `MultiSigRegistrar` with the rotated signer set;
   transfer `REGISTRAR_ROLE` on `LandRegistryAnchor` to the new
   instance; revoke from the old.
5. Anchored batches made by the compromised signer **remain valid**
   (the chain doesn't know the signer was compromised) but a
   `BREACH_NOTIFIED` audit event must accompany every batch from the
   compromise window.

### 5.4 Wrong NIN linked to wrong owner

If the breach is "data accuracy" (DPPA §10) rather than
confidentiality:

1. Confirm the misattribution via NIRA verification
   (`POST /api/v1/nira/verify`).
2. Emit an `erasure_tombstone` event for the wrong link
   (`AuditLedger.erasure_tombstone`, `app/audit/ledger.py:278`).
3. Re-create the correct `owners` row with the proper `nin_hash`.
4. The notification obligation is to the **misattributed citizen**
   (their NIN was associated with someone else's record), not to the
   data controller.

---

## 6. PDPO notification template

Address: Personal Data Protection Office, c/o NITA-U, Plot 7-9 Bombo
Road, P.O. Box 7080, Kampala, Uganda.

```
Date:        <YYYY-MM-DD>
Sent at:     <UTC timestamp>
Reference:   LG-DPPA-<incident-id>

Subject:     Notification of Personal Data Breach (DPPA-2019 §19)

To:          The Personal Data Protection Office
             c/o National Information Technology Authority Uganda (NITA-U)

Dear Sir / Madam,

Pursuant to §19 of the Data Protection and Privacy Act 2019, the
LandGuard Uganda data controller hereby notifies the Personal Data
Protection Office of a personal data breach.

1. NATURE OF THE BREACH
   <one paragraph summarising what happened, when it was detected, and
   the present containment status>

2. CATEGORIES AND APPROXIMATE NUMBER OF DATA SUBJECTS AFFECTED
   <e.g. "Approximately 1,200 citizens whose NIN-hash entries were
   accessible via the affected interface between 14:00 and 14:42 UTC
   on 2026-MM-DD. No raw NIN, no biometric template, and no phone
   number was exposed.">

3. CATEGORIES AND APPROXIMATE NUMBER OF RECORDS AFFECTED
   <enumerate by table — owners, parcels, transfers, etc.>

4. LIKELY CONSEQUENCES OF THE BREACH
   <plain-language risk assessment for affected citizens>

5. MEASURES TAKEN OR PROPOSED
   - Containment: <key rotation, role revocation, contract pause, etc.>
   - Recovery: <data restoration steps if applicable>
   - Future prevention: <controls being added>

6. CONTACT POINT
   Name:    <DPO name>
   Email:   dpo@landguard.ug
   Phone:   <+256-XXX-XXXXXX>
   Role:    Designated DPO under DPPA-2019 §28

The LandGuard data controller affirms its full cooperation with the
Personal Data Protection Office and will provide any further
information required.

Yours faithfully,

<signature>
<DPO name>, Data Protection Officer
LandGuard Uganda
```

---

## 7. Data-subject notification template (SMS)

160-character limit (USSD-friendly):

```
LandGuard alert: a security incident on <DATE> may have affected your
record. No raw ID number was leaked. Details: landguard.ug/notice
or *247*256*9# for help.
```

For citizens with no phone on file: notification via the District
Land Office of record (typically by registered post).

---

## 8. Public-statement requirements

The public statement at `https://landguard.ug/status` MUST include:

- The factual sequence of events with UTC timestamps.
- The scope of affected data (NIN hashes / phone hashes / names /
  none).
- The remediation actions taken and their dates.
- The DPO contact for citizen questions.
- A commitment to a 7-day full post-mortem.

It MUST NOT:

- Use vague language ("a small number of users may have been affected")
  when exact numbers are known.
- Attribute blame to a third party without their consent.
- Disclose ongoing forensic detail that would help a continuing
  attacker.

---

## 9. Audit-chain emission

Every step of the runbook is itself audit-emitted. The minimum set of
events:

| Event type | When | Payload |
|---|---|---|
| `INCIDENT_OPENED` | At t=0 | `{incident_id, severity, detector, summary_sha256}` |
| `CONTAINMENT_APPLIED` | At each containment action | `{incident_id, action, target, owner}` |
| `BREACH_NOTIFIED` | When PDPO notification is sent | `{incident_id, pdpo_reference, sent_at, sent_by}` |
| `DATA_SUBJECTS_NOTIFIED` | When SMS batch completes | `{incident_id, count, channel}` |
| `INCIDENT_CLOSED` | After post-mortem published | `{incident_id, closure_summary_sha256, postmortem_url}` |

These events are part of the **same chain** the verifier walks
(`backend/app/audit/verifier.py`), so the breach-notification audit
trail is itself tamper-evident.

---

## 10. Dry-run drill cadence

The Steering Committee runs a dry-run drill **once per quarter** with
a synthetic incident (no production data touched). Documented in
`docs/rehearsal/dppa-drill-YYYY-Q<n>.md`. A drill that takes longer
than 72 hours to complete the documented steps is itself a Sev-3.

---

## 11. Cross-references

- DPPA-2019 §19, §26, §28 (Republic of Uganda)
- `docs/SLA_TARGETS.md` §6, §7
- `docs/GOVERNANCE.md` (compliance map)
- `docs/audit/THREAT_MODEL.md` (informs detection)
- `MAINTAINERS.md` (out-of-band escalation path for key-touching changes)
- `backend/app/audit/ledger.py:278` (`erasure_tombstone` implementation)
