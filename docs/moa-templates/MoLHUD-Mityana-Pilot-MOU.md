# Memorandum of Understanding — LandGuard Pilot, Mityana District

**Between**

1. **The Ministry of Lands, Housing and Urban Development** (MoLHUD), represented
   by the Permanent Secretary, P.O. Box 7096, Kampala (the "Ministry");
2. **The Mityana District Land Board**, represented by its Chairperson, c/o
   Mityana District Local Government, P.O. Box [—], Mityana (the "District");
3. **The National Information Technology Authority — Uganda** (NITA-U),
   represented by the Executive Director, P.O. Box 33151, Kampala ("NITA-U");
4. **LandGuard Uganda**, c/o [—], represented by the Project Lead, with
   contact ``mpairwelauben75@gmail.com`` ("LandGuard").

Collectively, **the Parties**.

---

## 1. Purpose

The Parties enter into this Memorandum to operate a six-month pilot of the
LandGuard Uganda blockchain-enhanced land titling support system in Mityana
District, beginning **1 October 2026** and concluding **31 March 2027**, with
the objective of evaluating cryptographic tamper-evidence, AI-assisted fraud
detection, and public verifiability as complements to existing land
administration in Uganda.

## 2. Scope of the pilot

2.1 LandGuard operates as a **complement** to, not a replacement of, the
    National Land Information System (NLIS). The Ministry's existing records
    of authority remain the source of truth for legal title; LandGuard
    produces a tamper-evident audit chain and on-chain anchor receipts that
    reference NLIS records.

2.2 During the pilot the Parties target:

    (a) at least **200 titles issued and anchored** to the public blockchain;
    (b) at least **500 public verifications** (via QR code, USSD, or SMS);
    (c) at least **one fraud case detected by the AI scorer and reviewed
        by a Mityana Land Officer**, with the human-in-the-loop workflow
        observed end-to-end;
    (d) at least **one third-party verification of a title by a Ugandan
        commercial bank** during loan origination, captured as a case study;
    (e) **≥ 90% citizen satisfaction** in a post-pilot survey administered
        by an independent Ugandan academic partner.

2.3 The pilot does NOT include cross-district anchoring, customary tenure
    workflows requiring Communal Land Association ratification (those
    require a separate scope amendment), or replacement of any existing
    MoLHUD process.

## 3. Roles and responsibilities

### 3.1 The Ministry of Lands

(a) Designates a senior officer to chair the LandGuard Steering Committee.
(b) Holds **Signer Key #1** of the 3-of-5 ``MultiSigRegistrar`` (Custody:
    HSM in MoLHUD ICT centre; see ``docs/CUSTODY.md``).
(c) Authorises read access to relevant NLIS records for the pilot district.
(d) Provides one Recorder and one Registrar of Titles for training and
    daily operations during the pilot.

### 3.2 Mityana District Land Board

(a) Designates the District Land Board Chair as **Signer #3** of the
    ``MultiSigRegistrar``.
(b) Identifies the District Land Officer who will act as primary fraud
    reviewer (the human-in-the-loop role).
(c) Hosts the LandGuard backend service on infrastructure approved by
    NITA-U (see §3.3 below).

### 3.3 NITA-U

(a) Holds **Signer Key #2** of the ``MultiSigRegistrar`` (Custody: HSM in
    NITA-U TIER III data centre).
(b) Operates the NIRA bridge (``app/nira/live_client.py``) under the
    NIRA-NITA-U integration agreement.
(c) Performs an OWASP ASVS Level 2 assessment prior to go-live and
    quarterly thereafter; reports findings to the Steering Committee.
(d) Provides API gateway capacity sized for ≥ 1,000 verifications/min.

### 3.4 LandGuard

(a) Operates the LandGuard backend, frontend, and on-chain anchor service
    under the day-to-day technical leadership of its Project Lead.
(b) Holds **Signer Key #4** of the ``MultiSigRegistrar`` (Custody: cloud
    KMS separated from application servers).
(c) Trains designated staff (curriculum: ``docs/training/registrar-curriculum.md``,
    8 hours classroom + 4 hours supervised use).
(d) Publishes the source code under an OSI-approved open-source licence and
    keeps the GitHub repository public throughout the pilot.
(e) Conducts the quarterly demographic-parity audit
    (``scripts/fraud_parity_audit.py``) and publishes results.

### 3.5 Independent observer (signature pending)

The Parties agree to invite an independent Ugandan academic partner
(default proposal: **Makerere University College of Computing and
Information Sciences**) to:

(a) Hold **Signer Key #5** of the ``MultiSigRegistrar``.
(b) Conduct an independent smart-contract code review prior to go-live.
(c) Observe quarterly Steering Committee meetings.
(d) Publish an annual public review of the pilot.

## 4. Data protection & sovereignty

4.1 No personally identifiable information leaves Uganda. The on-chain
    anchor contains only Merkle roots of hashes; no NIN, name, or
    location is ever broadcast.

4.2 Each Party agrees to comply with the **Uganda Data Protection and
    Privacy Act (2019)**. LandGuard registers a Data Protection Officer
    with the Personal Data Protection Office (PDPO) within 30 days of
    pilot commencement.

4.3 Citizens have the rights of access, rectification, and erasure as
    defined in the DPPA. The erasure pathway uses the
    ``erasure_tombstone`` mechanism documented in
    ``docs/GOVERNANCE.md``.

4.4 Cryptographic key custody follows ``docs/CUSTODY.md``. No single
    Party can anchor a batch unilaterally; three of five Signer Keys
    must concur on every anchor.

## 5. Governance

5.1 The Steering Committee meets quarterly. Standing members: one
    representative from each of the four Parties + the Independent
    Observer. Decisions require consensus; if consensus fails, MoLHUD
    has the deciding vote on policy questions and NITA-U on security
    questions.

5.2 Changes to the AI scorer require:
    (a) a written model-card commit in ``docs/model-cards/``;
    (b) written go-live notes signed by LandGuard and the Independent
        Observer;
    (c) a parity audit run on the new version before deployment.

5.3 The MoICT&NG National Innovator Registry receives a quarterly written
    update for the duration of the pilot.

## 6. Costs

6.1 Infrastructure (cloud, anchoring, USSD shortcode): borne by LandGuard
    under its existing showcase grant for the duration of the pilot.

6.2 Training, internal IT support, and signer-HSM custody: borne by the
    respective Parties (MoLHUD, NITA-U, District).

6.3 Post-pilot continuation is contingent on a renewed agreement that
    addresses operational cost-recovery; this MOU does not commit any
    Party to operating costs beyond the pilot end-date.

## 7. Term and termination

7.1 This Memorandum enters into force on the date of last signature and
    terminates on **31 March 2027**, subject to:

    (a) **immediate suspension** by any Party in the event of a confirmed
        security incident or data-protection breach; or
    (b) **early termination** by any Party with thirty (30) days' written
        notice to the others.

7.2 On termination, anchor records remain on-chain (they cannot be
    reversed). LandGuard hands over a copy of the off-chain audit ledger
    to MoLHUD and decommissions its operational services within 60 days.

## 8. Intellectual property & open source

The LandGuard source code remains under its open-source licence. The
Ministry, the District, NITA-U, and the Independent Observer each have
perpetual, royalty-free, sublicensable rights to use, modify, and operate
the software for non-commercial public-administration purposes within
Uganda.

## 9. Dispute resolution

Disputes arising under this Memorandum will first be referred to the
Steering Committee for good-faith resolution. Unresolved disputes will be
referred to the Centre for Arbitration and Dispute Resolution (CADER) in
Kampala under Ugandan law.

---

## 10. Signatures

| Party | Name | Signature | Date |
|---|---|---|---|
| Permanent Secretary, MoLHUD | _______________ | _______________ | __________ |
| Chairperson, Mityana DLB | _______________ | _______________ | __________ |
| Executive Director, NITA-U | _______________ | _______________ | __________ |
| Project Lead, LandGuard | _______________ | _______________ | __________ |
| Independent Observer (Makerere CSL) | _______________ | _______________ | __________ |

---

*This template is supplied as part of the LandGuard prototype repository
and is intended as a starting point for negotiation. The final binding
instrument should be reviewed by counsel for each Party.*
