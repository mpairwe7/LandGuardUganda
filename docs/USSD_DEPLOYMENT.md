# USSD / SMS Deployment

Smartphone penetration in rural Uganda is ~30–40%. Title verification that
requires a smartphone leaves out the people who need it most. LandGuard ships
a feature-phone pathway that mirrors the smartphone PWA's public verifier.

## Flow

```
*247*256# → CON Welcome to LandGuard Uganda
            1. Verify title
            2. Check parcel status
            3. Help / contact District Land Office

User: 1
          → CON Enter title number (UG-DDD-TNNNNN/YYYY)

User: UG-MIT-T00007/2026
          → END ✓ Title UG-MIT-T00007/2026 VERIFIED on block 1234567 (tx 0xa1b2c3d4). Tamper-evident.
```

Same flow over SMS by texting the title number to a shortcode (e.g. 8444):
```
Citizen → 8444: UG-MIT-T00007/2026
8444    → Citizen: ✓ Title UG-MIT-T00007/2026 VERIFIED on block 1234567 (tx 0xa1b2c3d4). Tamper-evident.
```

## Gateway

We integrate with **Africa's Talking** (`https://africastalking.com`) — the
dominant Ugandan USSD/SMS aggregator, with NITA-U accreditation. Their
sandbox is free, the production API is paid per session.

### Local sandbox testing

1. Sign up at africastalking.com → Sandbox app.
2. Set the USSD callback to `https://<your-public-url>/api/v1/ussd` (use
   `ngrok` or Cloudflare Tunnel to expose `http://localhost:8000`).
3. Set the SMS inbound callback to `https://<your-public-url>/api/v1/sms/verify`.
4. Test from the Africa's Talking simulator.

### Production checklist

- [ ] UCC (Uganda Communications Commission) USSD shortcode assigned
      (typical timeline: 4–8 weeks; cost ~UGX 2M/year)
- [ ] Africa's Talking production account with NITA-U-compliant data
      residency clause
- [ ] Shortcode displayed on every printed title certificate alongside the QR
- [ ] Per-MNO routing tested (MTN, Airtel, Lyca, Uganda Telecom)
- [ ] Inbound-SMS limit of 1 verification per 10s per MSISDN (rate-limit
      via `slowapi` already in `app/middleware/limits.py`)
- [ ] Audit ledger inspected weekly for misuse: phone-number SHA256 frequency
      analysis to spot scraping (no raw MSISDN is ever logged)

## Privacy

The phone number is **never** stored in plaintext anywhere. The audit chain
records only `sha256(msisdn)` on every USSD/SMS verification — enough for
forensic correlation, insufficient for identity recovery. This matches the
Uganda DPPA 2019 "purpose limitation" principle: we verify, we don't
collect.

## Costs

- Africa's Talking USSD: ~UGX 60/session in production.
- 100,000 USSD verifications/year × UGX 60 = UGX 6M/year operating cost,
  budgeted in `docs/capacity-model.xlsx`.
- SMS replies: ~UGX 35/SMS. We discourage SMS in favour of USSD because
  USSD is interactive and cheaper.

## Why this is the equity win

A title-holder in Mityana with a Tecno B1F can verify their land's status
against a public blockchain in 30 seconds, for ~UGX 60, with no smartphone
required. This is the single most important inclusion property LandGuard
demonstrates. We invite evaluators to test it live on a feature phone at
the 25 June showcase booth.
