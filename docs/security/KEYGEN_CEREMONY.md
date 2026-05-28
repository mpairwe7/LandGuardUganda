# LandGuard maintainer PGP keygen ceremony

**Status:** procedure document. The ceremony must be performed once by
the LandGuard maintainer before 2026-06-01 to fulfil the commitment in
`MAINTAINERS.md`. This file is the record of *how* the key is generated;
the *result* (public key + fingerprint) ships in
`docs/security/landguard-maintainer.asc` and `MAINTAINERS.md`.

## Threat model for the key

- **Adversary:** an external attacker (no shell on the maintainer's
  machine, no GitHub account compromise, no NITA-U insider).
- **Asset:** the integrity of vulnerability reports — both the address
  they reach and the confidentiality of their contents.
- **Out of scope:** key compromise via physical seizure of the
  maintainer's device; that's the revocation-certificate's job, not
  the keygen's.

## Material requirements

- A computer running a current Linux/macOS with `gpg` (GnuPG 2.4+).
- ≥ 4 GB free entropy source: `/dev/urandom` is acceptable on a modern
  kernel; `haveged` or `rng-tools` recommended on long-running VMs.
- A printed backup destination (paper, with the maintainer's safe).
- ~ 15 minutes of uninterrupted attention.

## Ceremony procedure

> Run this on a personal machine the maintainer controls — **not** on a
> shared workstation, **not** on a CI runner, **not** inside this repo's
> dev container. The private key MUST NEVER touch this repository.

### 1. Pre-flight (in a clean shell)

```bash
gpg --version                 # require >= 2.4
ls ~/.gnupg/private-keys-v1.d # confirm no prior key for this purpose
```

### 2. Generate the key

```bash
gpg --batch --full-generate-key <<'EOF'
%no-protection
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: LandGuard Maintainer
Name-Comment: security contact — see MAINTAINERS.md
Name-Email: mpairwelauben75@gmail.com
Expire-Date: 2y
%commit
EOF
```

When prompted, set a strong passphrase. **Memorise it or write it
in the same safe as the paper backup — do NOT save it digitally.**

> `%no-protection` is removed by the prompt — gpg ignores the directive
> when used interactively. Verify with `gpg --list-secret-keys` that the
> key has SECs marked as "ssb" (passphrase-protected sub-keys).

### 3. Export the public key

```bash
KEYID=$(gpg --list-keys --keyid-format LONG mpairwelauben75@gmail.com \
        | sed -n 's|^pub  *rsa4096/\([A-F0-9]\{16\}\).*|\1|p' | head -1)
gpg --armor --export "$KEYID" > /tmp/landguard-maintainer.asc
gpg --fingerprint "$KEYID" | grep -A1 'pub' | tail -1 | tr -d ' '
```

The fingerprint output is the line that goes into `MAINTAINERS.md`.

### 4. Generate the revocation certificate

```bash
gpg --output ~/landguard-revoke-2026.asc --gen-revoke "$KEYID"
```

Move this file off the device immediately:

- Print it on paper, store with the passphrase backup.
- Optionally, also keep an encrypted copy on a hardware token (e.g.
  YubiKey HSM) — but the paper copy is the canonical fallback.

### 5. Commit only the public material

```bash
cp /tmp/landguard-maintainer.asc \
   "${REPO_ROOT}/docs/security/landguard-maintainer.asc"
# Now edit MAINTAINERS.md and replace the "pending" line with the
# fingerprint produced in step 3.
git add docs/security/landguard-maintainer.asc MAINTAINERS.md
git commit -m "security: publish maintainer PGP key"
```

### 6. Publish out-of-band

Post the fingerprint on the maintainer's GitHub profile (Profile →
Settings → "Bio" or a pinned gist) so that an attacker who manages to
push a forged key to this repo cannot get away with it.

## Renewal

The key expires after 2 years (`Expire-Date: 2y` above). Sixty days
before expiry, regenerate via this procedure with a new sub-key, push
a new `.asc`, update `MAINTAINERS.md`, and post a notice on the GitHub
profile pointing at the rollover commit.

## Compromise response

If you suspect the private key has been exposed:

1. Boot a clean machine, import the revocation certificate, and push
   the revocation to a keyserver:

   ```bash
   gpg --import landguard-revoke-2026.asc
   gpg --keyserver keys.openpgp.org --send-keys "$KEYID"
   ```

2. Generate a fresh key via this same procedure.
3. Update `MAINTAINERS.md` and `docs/security/landguard-maintainer.asc`.
4. File a `CHANGELOG.md` entry under "Security" describing the rotation
   without disclosing how the exposure happened (the latter goes into a
   private incident review).
