# Submission packet — MoICT&NG Government Systems Prototype Showcase

**Submission date:** 26 May 2026
**Showcase event:** 25 June 2026 · Serena Conference Centre, Kampala
**Thematic Area:** #2 — Land Administration & Titling Support

> This entire directory mirrors the operator-local layout used by the
> sibling `mpairwe7/HealthSyncUganda/submission/` packet — same toolchain,
> same audit-friendly artefacts, tailored to LandGuard Uganda. The PDF +
> HTML + PNG renders are committed alongside their `.md` and `.mmd`
> sources so a panellist can verify each diagram against its source.

> **Post-submission patches:** between submission (2026-05-26) and the
> 25 June showcase, four tagged releases have shipped against the same
> Crane Cloud deployment via the documented CI/CD pipeline. See
> [`POST_SUBMISSION_PATCHES.md`](./POST_SUBMISSION_PATCHES.md) for the
> audit-grade record; the rendered .docx / .pdf / .html in this
> directory remain the **frozen submission snapshot** as submitted.

## Contents

```
submission/
├── README.md                                       ← this file
├── LandGuard-Uganda-System-Description.md          ← markdown source (~22 KB)
├── LandGuard-Uganda-System-Description.html        ← HTML companion (~26 KB)
├── LandGuard-Uganda-System-Description.pdf         ← rendered PDF (~653 KB, ~8 A4 pages, diagrams inline)
├── LandGuard-Uganda-System-Description.docx        ← Word render (~538 KB, for review / track-changes)
├── diagrams/                                       ← Mermaid sources (.mmd)
│   ├── 01-c4-context.mmd
│   ├── 02-c4-container.mmd
│   ├── 03-resilience-flow.mmd
│   └── 04-security-boundaries.mmd
└── figures/                                        ← rendered PNGs (1920×1080, white background)
    ├── 01-c4-context.png
    ├── 02-c4-container.png
    ├── 03-resilience-flow.png
    └── 04-security-boundaries.png
```

The diagrams are **embedded inline** in the system-description PDF,
HTML, and DOCX so each document is self-contained. The standalone
PNGs in `figures/` remain available for evaluators who want to
enlarge a specific diagram or include one in a slide deck.

Last rendered: 2026-05-26 via `mmdc` (PNGs) + `weasyprint` (PDF) +
`pandoc` (DOCX), per the recipe in §3.

## How the diagrams are rendered (pipeline)

```
diagrams/*.mmd                          Mermaid text source
       │
       │  mmdc CLI (Node.js + Puppeteer)
       │  ├─ launches headless Chromium
       │  │  with --no-sandbox flags (Crane Cloud-grade
       │  │  sandboxes block the default Puppeteer profile)
       │  ├─ loads the Mermaid renderer in-page
       │  └─ renders each diagram to an SVG, then screenshots
       │     it to a 1920×1080 PNG on a white background
       ▼
figures/*.png                           rasterised diagram
       │
       │  Inline `<img src="figures/NN-name.png">` in the
       │  markdown source. Each render path picks them up
       │  via a base-path setting:
       │
       │   weasyprint   →  base_url="submission/"
       │   pandoc       →  --resource-path=submission
       │   browser/HTML →  same-folder relative resolution
       ▼
{PDF, HTML, DOCX}                       diagrams visible in
                                        each rendered format
```

The Mermaid `.mmd` files are committed alongside the rendered PNGs so
that:
1. **Audit reproducibility** — a panellist can re-render any diagram
   from source with one `mmdc` command and confirm the PNG hasn't
   been hand-edited (the byte-equal output proves the pipeline is
   deterministic).
2. **Editorial review** — diagram changes diff cleanly in git as text
   edits to the `.mmd` files; the PNG/PDF/DOCX re-renders follow.

## Build

### 1. Render the Mermaid diagrams to PNG

The rendering rig of record is **`@mermaid-js/mermaid-cli` (`mmdc`)** with
a Chromium `--no-sandbox` profile, since container/CI shells lack the
sandboxing privileges Puppeteer expects by default.

```bash
# One-off install
bun install -g @mermaid-js/mermaid-cli   # or: npm install -g @mermaid-js/mermaid-cli

# Puppeteer config to bypass the sandbox requirement
cat > /tmp/puppeteer-cfg.json <<'EOF'
{ "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
           "--disable-gpu", "--single-process"] }
EOF

# Render each diagram
cd submission
for fig in 01-c4-context 02-c4-container 03-resilience-flow 04-security-boundaries; do
  mmdc -i diagrams/${fig}.mmd \
       -o figures/${fig}.png \
       --backgroundColor white --width 1920 --height 1080 \
       --theme default \
       --puppeteerConfigFile /tmp/puppeteer-cfg.json
done
```

> **Mermaid gotchas hit while authoring (so you don't have to):**
> - HTML entities like `&nbsp;` inside `Note over X,Y:` text are parsed
>   as malformed arrows; use a regular space.
> - Semicolons inside `Note over X,Y:` text terminate the note prematurely;
>   use full stops.
> - Square brackets inside flowchart node labels (`X[name → '[erased]']`)
>   collide with the node-label delimiters; quote the whole label
>   (`X["name → '⟨erased⟩'"]`) or use a different bracket character.
>
> If `mmdc` is unavailable, paste each `.mmd` file into <https://mermaid.live>
> and **Actions → Download PNG**.

### 2. (Optional) Capture two real UI screenshots

The four diagrams above are sufficient for the narrative submission.
For a richer panel walk-through, add two screenshots taken from the
live deploy:

- **Public verifier verdict** — open <https://landguard-frontend-3d8aba74.renu-01.cranecloud.io/verify>, paste `UG-MIT-024718/2026`, press **Verify**. Screenshot the green "Title verified" panel with the Merkle proof visualization underneath.
- **Officer fraud-review queue** — open <https://landguard-frontend-3d8aba74.renu-01.cranecloud.io/officer> (role-switcher → LAND_OFFICER). Screenshot the queue showing the three seeded pending reviews (watchlist match, rapid resale, duplicate NIN).

Save them as `figures/05-public-verifier.png` and `figures/06-fraud-queue.png`.

### 3. Convert the system description to PDF — weasyprint path (no LaTeX)

The project uses **`weasyprint`** + Python's `markdown` library because
it's pure-Python (no LaTeX install), reliable on minimal container
images, and produces clean A4 output with images embedded inline.

```bash
cd <repo-root>

# One-off install if not present
pip install --user markdown weasyprint

python3 <<'PY'
import re
from pathlib import Path
import markdown
from weasyprint import HTML, CSS

md_text = Path("submission/LandGuard-Uganda-System-Description.md").read_text()
# Strip pandoc-style image attributes like { width=100% }
md_text = re.sub(r'\{\s*width=[^}]+\}', '', md_text)

body = markdown.markdown(
    md_text,
    extensions=["tables", "fenced_code", "attr_list"],
    output_format="html5",
)

# Forest-green palette matching the LandGuard design tokens
# (guard-700 = #1a5223). Tighter line-height keeps the doc to A4.
css = CSS(string="""
  @page { size: A4; margin: 1.4cm 1.5cm; }
  body { font-family: "DejaVu Sans","Inter",sans-serif; font-size: 9pt; line-height: 1.28; color: #111; }
  h1 { font-size: 16pt; color: #1a5223; margin: 0 0 0.3em 0; }
  h2 { font-size: 12.5pt; color: #1a5223; margin: 0.9em 0 0.25em 0; page-break-after: avoid; }
  h3 { font-size: 10.5pt; color: #1a5223; margin: 0.7em 0 0.2em 0; page-break-after: avoid; }
  p  { margin: 0.3em 0; }
  ul,ol { margin: 0.3em 0 0.5em 1.4em; padding: 0; }
  li { margin: 0.05em 0; }
  table { border-collapse: collapse; width: 100%; margin: 0.4em 0; font-size: 8pt; }
  th,td { border: 1px solid #ccc; padding: 2px 5px; text-align: left; vertical-align: top; }
  th { background: #f0f8f1; font-weight: bold; }
  code { font-family: "DejaVu Sans Mono",monospace; background: #f5f5f5; padding: 0 2px; font-size: 8pt; }
  pre  { background: #f5f5f5; padding: 4px 6px; border-left: 2px solid #1a5223; font-size: 7.5pt; page-break-inside: avoid; }
  hr   { border: none; border-top: 1px solid #ccc; margin: 0.6em 0; }
  a    { color: #1e40af; text-decoration: none; }
  blockquote { border-left: 2px solid #1a5223; padding-left: 6px; color: #444; font-style: italic; }
  img  { max-width: 100%; height: auto; page-break-inside: avoid; margin: 0.5em auto; display: block; }
  img + em { display: block; text-align: center; font-size: 8pt; color: #555; margin: 0.1em 0 0.6em 0; }
""")

html_doc = f"<!doctype html><html><head><meta charset='utf-8'></head><body>{body}</body></html>"

Path("submission/LandGuard-Uganda-System-Description.html").write_text(html_doc)

# base_url='submission/' lets weasyprint resolve figures/*.png references
pdf = HTML(string=html_doc, base_url="submission/").render(stylesheets=[css])
pdf.write_pdf("submission/LandGuard-Uganda-System-Description.pdf")
print(f"  pages: {len(pdf.pages)}, file: submission/LandGuard-Uganda-System-Description.pdf")
PY
```

**Last rendered result:** 8 pages, ~653 KB.

### 4. Convert the system description to DOCX — `pandoc` (for review / track-changes)

The DOCX render exists so reviewers can leave Word comments and
suggested edits before the next PDF pass; the markdown source remains
canonical. The pipeline is `pandoc` only — no LaTeX, no LibreOffice.

```bash
# One-off install. Static binary works without root.
mkdir -p /tmp/pandoc-bin && cd /tmp/pandoc-bin
curl -sfL https://github.com/jgm/pandoc/releases/download/3.6/pandoc-3.6-linux-amd64.tar.gz \
  -o pandoc.tar.gz
tar -xzf pandoc.tar.gz
PANDOC=/tmp/pandoc-bin/pandoc-3.6/bin/pandoc
# (On apt/dpkg systems: sudo apt-get install pandoc — version >= 2.19)

cd <repo-root>
$PANDOC submission/LandGuard-Uganda-System-Description.md \
  --resource-path=submission \
  --from=markdown+pipe_tables+fenced_code_blocks+yaml_metadata_block+link_attributes+implicit_figures \
  --to=docx \
  --output=submission/LandGuard-Uganda-System-Description.docx
```

`--resource-path=submission` resolves the `figures/*.png` references to
the same files the PDF embeds. The four diagrams land in
`word/media/rId*.png` inside the DOCX zip, byte-equal to the PNG
sources. Reviewers see them inline in Word / LibreOffice Writer with
no further steps.

**Last rendered result:** ~538 KB, all four diagrams embedded
(verifiable via `unzip -l submission/LandGuard-Uganda-System-Description.docx | grep media`).

If you prefer pandoc + LaTeX for the PDF (heavier toolchain, more
typographic control), the equivalent recipe is in the
HealthSyncUganda submission's git history.

## Pre-submission checklist

- [x] PDF includes all four diagrams inline (`01-c4-context`,
      `02-c4-container`, `03-resilience-flow`, `04-security-boundaries`)
- [x] DOCX render generated for review / track-changes (same four
      diagrams embedded in `word/media/`)
- [x] Mermaid `.mmd` sources committed alongside rendered PNGs so a
      reviewer can verify the diagram against the source
- [x] Repository URL on the cover page resolves publicly
      (<https://github.com/mpairwe7/LandGuardUganda>)
- [x] Live deploy URLs reachable + return HTTP 200 (`/readyz`,
      `/api/v1/anchors`, `/`, `/verify`, `/demo`)
- [x] No `[Pilot lead to populate]` or other unfilled placeholder
      markers in the PDF body
- [x] Contact details (`mpairwelauben75@gmail.com`) match
      `MAINTAINERS.md` and `docs/TEAM.md`
- [ ] Optional UI screenshots (`05-public-verifier`, `06-fraud-queue`)
      captured per §2 — narrative submission is complete without them
- [x] Internal markdown links + repo-relative paths resolve from
      repo root
- [x] CHANGELOG.md timeline up to date through commit `279b365`
      (`2026-05-26`)

## Verification entry point for the panel

Every claim in the submission is reproducible against the open
repository starting at:

- `docs/SHOWCASE_EVALUATION_MAPPING.md` — criterion-to-evidence map
  with reviewer-runnable verification commands.
- `docs/audit/CODEBASE_MAP.md` — file-by-file inventory, updated through
  commit `279b365`.
- `docs/audit/{THREAT_MODEL, PENTEST_SCOPE, AUDIT_PACKAGE}.md` — formal
  audit dossier.
- `CHANGELOG.md` — dated, reverse-chronological timeline of every
  security-relevant change.
- Live deploys (Crane Cloud RENU staging):
  - Frontend: <https://landguard-frontend-3d8aba74.renu-01.cranecloud.io>
  - Backend API: <https://landguard-backend-d1e66f33.renu-01.cranecloud.io>
  - Readiness: <https://landguard-backend-d1e66f33.renu-01.cranecloud.io/readyz>
  - Public anchors (no auth): <https://landguard-backend-d1e66f33.renu-01.cranecloud.io/api/v1/anchors>
  - OpenAPI schema: <https://landguard-backend-d1e66f33.renu-01.cranecloud.io/openapi.json>
  - Swagger UI: <https://landguard-backend-d1e66f33.renu-01.cranecloud.io/docs>

## Showcase walkthrough — five live acts panelists can run

Each act takes ≤2 minutes from a phone or laptop browser. Roles are
swapped via the top-bar `RoleSwitcher` on the deployed staging instance
(see `DEMO_RUNBOOK.md` for the canonical 12-minute presentation order).

### A. Citizen — verify a real title from the public verifier
1. Open <https://landguard-frontend-3d8aba74.renu-01.cranecloud.io/verify> on a phone.
2. Paste `UG-MIT-024718/2026` (Mrs. Sarah Nakato's hero parcel).
3. Press **Verify** → green "Title verified" + Merkle proof animation +
   on-chain receipt (batch ID, tx hash, block number).
4. Toggle the locale switcher to **Luganda** → the page re-renders
   in Luganda. (Stub translation; pending native-speaker review for
   the pilot.)

### B. Surveyor — register a parcel with real-time overlap detection
1. Role-switch to **SURVEYOR**, district **Mityana**.
2. Open `/surveyor/register`. Click three points on the MapLibre canvas
   to draw a polygon → Turf.js computes the area in hectares live and
   flags any conflict with an existing Mityana parcel.
3. Fill in tenure type (`MAILO` / `FREEHOLD` / `LEASEHOLD` /
   `CUSTOMARY`) and sub-county; submit. The UPI is auto-formatted as
   `UG-MIT-<parcel-number>/2026`.

### C. Registrar — issue a title and watch its Merkle root commit
1. Role-switch to **REGISTRAR**.
2. `/registrar` → enter a parcel UPI + owner ID → **Issue title**.
3. The Merkle-proof visualizer animates leaf → siblings → root.
4. Click **Force anchor flush** → within ~10 s the public
   `/anchors` page picks up the new batch with its tx hash and block.

### D. Officer — review a fraud signal with explainable AI
1. Role-switch to **LAND_OFFICER**.
2. `/officer` shows three seeded pending reviews:
   - "Patrick Bwambale — watchlist match" (risk 92, action BLOCK)
   - "Rapid resale 9 days after acquisition" (risk 71, action FLAG)
   - "Duplicate NIN, Mityana + Gulu within 24 h" (risk 64, action FLAG)
3. Open one → see the per-rule signal contributions + a mandatory
   `notes >= 4 chars` field on **Affirm** / **Dismiss**.
4. Only `Affirm` produces a `FRAUD_HUMAN_AFFIRMED` audit event that
   actually moves a title to `FROZEN`. No auto-FREEZE — the
   human-in-the-loop invariant is documented in
   `docs/AI_ETHICS_CHARTER.md`.

### E. Resilience — kill the chain RPC live on stage
1. Open `/demo` (gated by `app_env != "production"`).
2. Press **Kill RPC** → anchor_breaker → `open`; the global header
   `ChainStatusBeacon` flips amber ("Chain queued").
3. Issue another title in another tab → it succeeds; its event sits
   in the unanchored queue.
4. Press **Restore RPC** → anchor_breaker → `half_open` → `closed`;
   the queue drains; the new batch confirms on-chain; the beacon
   flips green.

## Mobile usability (a phone in a rural facility)

- Resize the browser to 393×851 (Pixel 5) or open on a phone.
- Top headers collapse to a **hamburger drawer** revealing the full
  navigation; on the (app) console the left sidebar collapses to a
  drawer too.
- Tap targets ≥ 44×44 px per WCAG 2.5.5 / Apple HIG.
- `frontend/e2e/mobile.spec.ts` exercises this flow on every CI run:
  4 routes for horizontal-overflow regression, both hamburgers, plus
  axe-core a11y on `/verify`.

## Last verification run (commit `8ccb03c`)

- **CI:** 8/8 jobs ✓ (Backend, Frontend, Docker build verify x2,
  Accessibility, OSV, Contracts, SBOM).
- **Build & push:** ✓ — both images on Docker Hub:
  `landwind/landguard-uganda-{backend,frontend}:0.1.0-showcase-8ccb03c`.
- **Deploy to Crane Cloud:** ✓ all 9 steps.
- **Live state:** `/readyz` → `{db: ok, breaker: closed, block:
  1000001}`; all 11 frontend routes HTTP 200.
- **Backend pytest:** 32 / 32 passing locally.
- **Frontend e2e (smoke + flows + a11y):** 24 / 24 desktop +
  8 / 8 mobile (Pixel 5).
