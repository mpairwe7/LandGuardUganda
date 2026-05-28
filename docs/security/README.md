# Security contact materials

This directory holds the cryptographic and procedural artefacts that let
external researchers reach the LandGuard maintainer through a verifiable
channel.

| File | Purpose | Sensitivity |
|---|---|---|
| `landguard-maintainer.asc` | Public PGP key for the LandGuard maintainer | Public — safe to publish |
| `KEYGEN_CEREMONY.md` | The procedure used to mint the key above | Public |
| **NOT IN THIS DIRECTORY** — the matching private key | Never committed; lives only on the maintainer's air-gapped device | High |

## Why a key, not just an email

`MAINTAINERS.md` commits to a security-contact pathway. Anyone reporting
a vulnerability needs to know:

1. The recipient address is genuine and not a phishing redirect.
2. Their report is not legible to an MITM on the way to the maintainer.

A published PGP key, fingerprint-pinned in `MAINTAINERS.md`, satisfies
both. The key is **not** used for git commit signing (that's an
orthogonal decision — see commit messages).

## Reproducing the published fingerprint

Every reader can verify that the fingerprint in `MAINTAINERS.md` matches
the published `.asc` file:

```bash
gpg --show-keys docs/security/landguard-maintainer.asc \
  | grep -E "^\s+[A-F0-9]{40}\s*$" \
  | tr -d ' '
```

The output must equal the fingerprint line in `MAINTAINERS.md`. If they
disagree, the report channel is compromised — escalate via the
out-of-band fallback in `MAINTAINERS.md`.
