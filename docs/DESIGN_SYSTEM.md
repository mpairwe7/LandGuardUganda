# LandGuard Uganda — Design System

**A design specification for a Blockchain-Enhanced Land Administration & Titling Support System.**

Audience: government evaluators (MoICT&NG National Innovator Registry, MoLHUD,
NITA-U), the LandGuard engineering team, and any future implementation
partner. The system is implemented in `frontend/tailwind.config.ts` (tokens)
and `frontend/src/styles/globals.css` (component classes); every claim below
is backed by a token or class you can grep for.

---

## Design philosophy

LandGuard is an instrument of state authority. Citizens consult it to prove
ownership of family land; officers use it to commit administrative actions
that will live on a public blockchain forever. The interface must therefore
feel **closer to a passport office than to a SaaS dashboard** — and closer
to `mlhud.go.ug` than to a consumer fintech.

Three operating principles flow from this:

1. **Receipts over claims.** Every page that asserts a state shows the proof
   of that state — a hash, a transaction id, a timestamp, a block number.
   The Merkle visualiser and the title certificate are the canonical
   examples.
2. **Authority is restraint.** Government documents do not gradient, glow,
   or animate decoratively. Where ordinary apps decorate, LandGuard
   subtracts.
3. **Inclusion before delight.** A coffee farmer in Mityana with a feature
   phone must be able to verify her own title. Animations and visual
   sophistication are conditional on this baseline working first.

The rest of the document specifies how this philosophy is encoded.

---

## 1. Colour palette

### 1.1 Primary — Uganda Forest Green (`guard`)

The primary palette is calibrated against the deep institutional green used
across MoICT&NG digital estates (`ict.go.ug`, `nita.go.ug`, `mlhud.go.ug`).
We deliberately landed on a darker tone than commercial "green" brands —
the brief is government, not lifestyle.

| Token        | Hex       | Where it lives                              |
| ---          | ---       | ---                                         |
| `guard-50`   | `#f0f8f1` | Subtle hover fills, citizen-page accents    |
| `guard-100`  | `#d8ecd9` | Step badges, callout backgrounds            |
| `guard-200`  | `#b3d9b6` | Hairline borders on green surfaces          |
| `guard-300`  | `#82bf87` | Hover ring on links and disabled-but-hover  |
| `guard-400`  | `#4f9e57` | (Reserved — rarely used)                    |
| `guard-500`  | `#2f8138` | (Reserved — rarely used)                    |
| `guard-600`  | `#20672a` | Focus rings and button hover state          |
| `guard-700`  | `#1a5223` | **Primary action background, brand voice**  |
| `guard-800`  | `#16441e` | Officer sidebar accent borders              |
| `guard-900`  | `#133819` | Officer sidebar surface                     |
| `guard-950`  | `#08200d` | Officer console header band, theme colour   |

The progression compresses at the dark end — `guard-700` through `-950` are
visually close because they all need to be readable on white text while
still differentiating chrome (sidebar) from emphasis (header).

### 1.2 Accent — Uganda Gold (`seal`)

Gold is the most expensive colour in the system. Its use is restricted to
**state-authority signals** — the certificate seal, the on-chain
confirmation pill, the ministry attribution band. If three or more gold
elements appear on a single screen, one of them is a bug.

| Token       | Hex       | Where it lives                                  |
| ---         | ---       | ---                                             |
| `seal-50`   | `#fdf9ed` | Certificate background, gold-themed callouts    |
| `seal-100`  | `#faf0ca` | Border on `card-document`                       |
| `seal-300`  | `#efc94e` | "On-chain" pill border                          |
| `seal-400`  | `#e8b425` | Certificate header band; ministry-band accents  |
| `seal-700`  | `#925b13` | Gold ink (text-on-cream)                        |

### 1.3 Semantic — status colours

Status colours are paired with icons (WCAG §1.4.1) and `aria-label`s
(WCAG §1.3.1). Colour alone never carries meaning.

| Token             | Hex       | Meaning                                | Icon          |
| ---               | ---       | ---                                    | ---           |
| `status-verified` | `#15803d` | Anchored on chain · valid · complete   | `ShieldCheck` |
| `status-pending`  | `#b45309` | Awaiting anchor · awaiting review      | `Clock`       |
| `status-flag`     | `#c2410c` | **AI-screened** for review (not a decision) | `AlertTriangle` |
| `status-frozen`   | `#b91c1c` | **Human-affirmed** freeze              | `Lock`        |
| `status-chain`    | `#1e40af` | Generic on-chain reference             | `Link`        |
| `status-neutral`  | `#475569` | Unstated / default                     | `CheckCircle2`|

**Critical rule from the AI Ethics Charter:** orange (`status-flag`) is for
ML-flagged events; red (`status-frozen`) is reserved for human-affirmed
freezes. The colour communicates *the locus of accountability*. The fraud
review surface lives this distinction.

### 1.4 Neutrals — Slate

All text, borders, surfaces, and chrome that are not `guard`/`seal`/status
use Tailwind's default `slate-*` ramp. Slate (cool grey) reads as more
institutional than warm grey on white paper; it harmonises with the deep
green at the dark end of the palette without going muddy.

| Use                    | Token       | Hex       |
| ---                    | ---         | ---       |
| Page canvas            | `slate-50`  | `#f8fafc` |
| Surface (cards, paper) | `white`     | `#ffffff` |
| Default border         | `slate-200` | `#e2e8f0` |
| Body text              | `slate-700` | `#334155` |
| Heading text           | `slate-900` | `#0f172a` |
| Muted / caption text   | `slate-500` | `#64748b` |

### 1.5 How colour communicates trust

- **Restraint** — three palettes + slate, no more. A page using six brand
  colours looks like a startup; a page using three looks like a ministry.
- **The "gold tax"** — every gold element on screen must be paying for itself.
  This budgets the eye for the moments that matter (certificate seal,
  on-chain confirmation, ministry attribution).
- **Status hierarchy without panic** — pending is amber, ML-flagged is
  orange, human-affirmed-freeze is red. Citizens get a measured progression
  even in the worst case (no jarring red unless an officer has personally
  decided).

---

## 2. Typography

### 2.1 Type family — IBM Plex

| Variant         | Family             | Loaded via                   |
| ---             | ---                | ---                          |
| Body and UI     | IBM Plex Sans      | `next/font/google` self-hosted at build |
| Documents and institutional headlines | IBM Plex Serif | `next/font/google` self-hosted at build |
| Identifiers and hashes | IBM Plex Mono | `next/font/google` self-hosted at build |

Why IBM Plex:

- **Wide x-height + open apertures.** Stays legible at 12 px (the smallest
  size used in the officer console) and on low-DPI projector renderings at
  the showcase.
- **Generous tabular numerals.** Critical for land records — parcel sizes,
  block numbers, and UPI sequences must line up vertically across rows.
  Tabular numerals are enabled at the `<body>` level via
  `[font-feature-settings:'tnum','lnum']`.
- **Government provenance.** Plex was commissioned by IBM as an
  institutional voice; it reads as serious rather than promotional. Avoids
  the "tech-bro" association of Inter / Geist / Söhne.
- **Self-hosted, no runtime Google Fonts.** Important for the
  low-bandwidth PWA story and for DPPA-2019 data-residency posture
  (no third-party beacon).

### 2.2 Type scale

The scale targets a 1.125 ratio in the small sizes (UI density) and 1.250
in the large sizes (institutional headlines). Token names match Tailwind.

| Token       | Size      | Line height | Where it lives                                 |
| ---         | ---       | ---         | ---                                            |
| `text-caption` | 12 / 16 |             | Eyebrow labels, table headers, captions        |
| `text-xs`   | 13 / 18    |             | Helper text, breadcrumbs                       |
| `text-sm`   | 14 / 20    |             | Body small (default for officer console)       |
| `text-base` | 16 / 24    |             | Body (default for citizen surfaces)            |
| `text-lg`   | 18 / 28    |             | Card titles, section leads                     |
| `text-xl`   | 20 / 28    |             | Sub-headlines, certificate body                |
| `text-2xl`  | 24 / 32    |             | Page H1 (officer console)                      |
| `text-3xl`  | 30 / 36    |             | Certificate "Certificate of Title"             |
| `text-4xl`  | 36 / 40    |             | Public-landing H1 (mobile)                     |
| `text-display` | 48 / 56  |             | Public-landing H1 (desktop)                    |

Letter-spacing tightens at large sizes (`-0.015em` at 3xl, `-0.025em` at
display) so headlines don't fall apart at projector scale.

### 2.3 Hierarchy rules for legal information

- **One H1 per page.** The H1 names the legal subject of the page
  ("Certificate of Title", "Issue title", "My parcels"). Never decorative.
- **Sub-section headings** (`text-xl font-serif`) use Plex Serif. The serif
  signals "this is a document, not a feature."
- **Identifiers in monospace.** Parcel UPIs, NIN-hashes, block numbers,
  transaction hashes — always `font-mono`. Treating IDs as code makes
  copy-paste accidents visible and aligns columns in tables.
- **Captions for evidence.** Every receipt-like element (timestamp, block
  number, registrar id) gets a `text-caption` label above it in
  `tracking-[0.16em] uppercase`, so the eye reads the label first and the
  evidence second.

---

## 3. Spacing & layout

### 3.1 Spacing scale

Tailwind's default 4-px-rhythm scale (`p-1` = 4 px through `p-24` = 96 px).
Specific load-bearing values:

| Use                        | Token         |
| ---                        | ---           |
| Inside a status pill       | `gap-1.5`     |
| Card internal padding      | `p-6` (24 px) |
| Document (certificate) pad | `p-10` (40 px) |
| Section vertical rhythm    | `space-y-6` to `space-y-8` |
| Page top padding (officer) | `py-8` (32 px) |
| Page top padding (citizen) | `py-12` to `py-20` |

### 3.2 Canvases

Two max-widths, anchored to the audience:

| Constraint    | Value    | Where it applies                             |
| ---           | ---      | ---                                          |
| `max-w-citizen` | 896 px | Citizen-facing reading surfaces              |
| `max-w-officer` | 1280 px | Officer console, public landing, anchors browser |

The citizen canvas is narrower because citizens are reading their own
records — narrow column, larger type, fewer distractions. The officer
canvas is wider because officers triage queues and need lateral space for
data + actions.

### 3.3 Cards (three weights)

| Class           | Border    | Shadow          | Use                          |
| ---             | ---       | ---             | ---                          |
| `card-surface`  | `slate-200` | none          | Default content surface      |
| `card-elevated` | `slate-200` | `shadow-card` | Floats above the page        |
| `card-document` | `seal-100`  | `shadow-document` | Printable artefacts (title) |

Three is the right number. Two is not enough (no way to elevate without
shouting); four crosses into clutter. The deepest shadow in the entire
system is `shadow-document` (used on the title certificate) and it exists
to suggest paper, not to add depth chrome.

State accents — `state-pending`, `state-flag`, `state-frozen`,
`state-verified` — are 2-px left borders applied to a card. They let an
officer scan a queue by colour without consuming a pill slot inside the
card.

### 3.4 Data tables

Tables are the heart of land-record UX. Every table uses `.data-table`:

- **Sticky header** (`thead th sticky top-0`) — officers scroll through 200
  parcels and need column labels in view.
- **Numeric columns right-aligned with `tabular-nums`** — areas, prices,
  consideration values.
- **Identifier columns in `font-mono`** with the `.identifier` modifier —
  UPIs, hashes.
- **Zebra rows at 60% slate-50** — visible at projector scale but not noisy
  on screen.
- **Hover row** sits on `guard-50` — links the table to brand without
  shouting.

### 3.5 Grids

Two grids matter:

- **Sidebar + content** (officer console): `grid-cols-[16rem_1fr]`. The
  sidebar is a fixed 256 px so the eye doesn't have to recalibrate when
  pages change.
- **Two-up data block** (certificate, registrar console):
  `grid-cols-2 gap-x-10 gap-y-4`. Generous horizontal gutter so the eye
  reads each label-value pair as a unit.

---

## 4. Theme & visual identity

### 4.1 Buttons — the only four allowed

There are exactly four button variants. Anything else is a bug.

| Variant       | Use                                          | Visual                                    |
| ---           | ---                                          | ---                                       |
| `primary`     | The single most-important action on a screen | Solid `guard-700` fill, white text        |
| `secondary`   | Supporting actions; never primary's twin     | White surface, `slate-300` border         |
| `tertiary`    | Inline text-style action ("view details")    | `guard-700` text, underline-on-hover      |
| `destructive` | Affirmative freeze, revoke, delete           | Solid `status-frozen` fill, white text    |

Two non-negotiable rules:

- **At most one primary per screen.** If you find yourself adding a second,
  one of them is actually secondary.
- **Destructive always pairs with confirmation at the call site.** The
  officer review queue's "Affirm — freeze parcel" is the canonical example:
  notes are required (≥4 chars) before the button enables.

The button component lives at `src/components/common/Button.tsx`. Adding
inline `<button>` styles in pages is a code-review smell.

### 4.2 Forms

- **Labels above inputs**, not floating, not placeholder-only. Legal
  documents need labels that survive when the input is filled.
- **Help text below the input** in `slate-500`, error text in `status-frozen`.
- **Input height = 40 px** (`h-10`). Touch-friendly on a 7" tablet in the
  field; not so big it dominates the dashboard.
- **Monospace inputs** for identifiers (`field-input-mono`) — UPIs, NINs,
  block numbers. The font choice signals "this is a code, not free text".
- **Focus ring** is `guard-600` at 20 % opacity, 2-px-wide. Visible on every
  surface without dominating.

### 4.3 Modals

LandGuard avoids modals where possible — government workflow is linear, not
overlay-driven. The exceptions:

- **Confirmations** for destructive actions (freeze, revoke). 480 px max
  width, `card-elevated`, primary action is destructive and labelled with
  the verb ("Freeze parcel") not the affirmation ("OK").
- **Image / map zoom** — full-bleed dark backdrop, ESC + outside-click both
  close, focus returns to the originating button.

Sheets (slide-overs) are not used. Drawer UI feels SaaS; we don't.

### 4.4 Dashboards (officer console)

The officer console is the highest-density surface in the system.
Design rules:

- **Dark chrome, light content.** Header band is `guard-950`, sidebar is
  `guard-900` — these signal "you are working inside the system." The
  content well is `slate-50` so documents and certificates read like
  government paper.
- **Sidebar navigation is grouped by role** (Citizen / Surveyor / Land
  Officer / Registrar / Auditor), not by feature. The role groupings match
  how MoLHUD is organisationally structured — a real Land Officer sees the
  officer group as "my work" and the others as "context."
- **Active district picker lives at the top of the sidebar.** District is
  the most consequential filter in the system; it gates every query and
  every audit-chain write. Keeping it visible and editable defends against
  the "wrong-district-on-Tuesday" class of bugs.

### 4.5 Blockchain visual language

This is where most government UX would fail. Three rules:

1. **The cryptography is the page.** The Merkle proof visualiser doesn't
   *animate around* the proof; the proof is the content. Each row reveals
   in ≤0.32 s, the root node carries the gold "On chain" pill, the
   transaction / block / chain-id fields settle in last.
2. **No gradients, no glow, no neon.** This is a government document, not
   a crypto product page. Solid lines only.
3. **Animations end.** Nothing in the chain visualisation loops except the
   "pending" pulse (`animate-pulse-slow`, 2.4 s) — and that loops only
   because the user is genuinely waiting.

The visualiser also doubles as **proof of byte-identical behaviour** —
the same proof verifies in the Solidity contract and in the
TypeScript-side `merkle.ts`. This is the showcase moment for evaluators:
the visualisation is not a metaphor, it is the actual computation.

### 4.6 Verification status (the public verifier)

The public verifier is the surface most non-LandGuard people will ever
see. Design rules:

- **One question per screen.** "Is this title valid?" is the only thing
  the verifier answers. UPI + scan-QR + result. No nav, no chrome.
- **The verdict is iconic + colour + plain language.** A green
  `ShieldCheck`, "Verified on chain", and the timestamp. Or an amber
  `Clock`, "Anchored off-chain (anchor pending)", and "Still legally valid."
  Or a red `Lock`, "This title is FROZEN — contact your District Land
  Office." Plain English, no jargon.
- **The receipts sit below the verdict.** Block number, tx hash, anchored-at
  timestamp — all `font-mono`, all copyable. A journalist or NGO worker
  who wants to verify independently has everything they need.

### 4.7 Fraud alerts (the AI Ethics surface)

Fraud is the place where design carries the most ethical weight. The rules
encode the AI Ethics Charter:

- **Orange for ML, red for human.** ML-flagged events use `status-flag`
  (orange). Only a human-affirmed freeze gets `status-frozen` (red). This
  is the visual proof of the human-in-the-loop policy.
- **Risk score is a number, not a meter.** A meter implies a continuous
  spectrum; a number is auditable and comparable across cases.
- **Plain-language signals.** Each rule that fires gets a human-readable
  label ("Boundary overlap detected", not `geometry_overlap`). The
  technical rule name appears only on hover or in the JSON audit trail.
- **The disclaimer is fixed.** Every fraud surface carries the line: "This
  is a decision-support indicator. No parcel is frozen without affirmative
  action by a LAND_OFFICER or REGISTRAR. Citizens affected by a flag may
  appeal at any District Land Office or via USSD *247*256*9#." This copy
  is non-negotiable and not configurable.

---

## 5. Project-specific adaptations

### 5.1 Citizen view vs Officer view

| Aspect                | Citizen surface                  | Officer console                            |
| ---                   | ---                              | ---                                        |
| Canvas                | Centered, `max-w-citizen` (896 px) | Full bleed, `max-w-officer` (1280 px)      |
| Chrome                | Light (white header, slate page) | Dark (`guard-950` header, `guard-900` sidebar) |
| Base type size        | `text-base` (16 px)              | `text-sm` (14 px)                          |
| Information density   | Low — one decision per page      | High — triage queues, tables of 50+ rows   |
| Vocabulary            | Plain English, no rule names     | Technical labels visible, scorer versions  |
| PII                   | The user's own, shown plainly    | Other citizens' — gated by **Redact mode** |
| Primary action        | "View certificate", "Verify"     | "Affirm — freeze parcel", "Issue title"    |
| Help text             | Long-form, contextual            | Tooltip-level, assumes domain knowledge    |

**Redact mode** is the load-bearing officer-console feature. Officers can
toggle every PII element (NIN, name, registrar id, notes) to blur-on-screen
in one click — the visual equivalent of the privacy screens that ministry
staff use today. Hovering a redacted element briefly reveals it; the
preference is per-session and not persisted (so an officer cannot
accidentally walk away from a public screen with redaction off).

### 5.2 Representing blockchain transactions

A transaction in LandGuard has up to seven attributes worth showing. We
display them in this priority order:

1. **Anchor status** — `verified` / `pending` (status pill, the first thing
   read).
2. **Block number** — `font-mono tabular-nums`, copyable.
3. **Transaction hash** — `font-mono`, head-truncated (e.g. `0x4a2f8c…b71d`),
   copyable.
4. **Anchored at** — human timestamp ("12 Jun 2026 · 14:23 UTC").
5. **Chain ID** — only when ambiguous (Anvil vs Sepolia vs production).
6. **Batch ID** — for auditors who want to find the batch independently.
7. **Merkle root** — last; auditors who need it, find it.

Hash truncation always shows `head + ellipsis + tail` (`HashDisplay`
component). Showing only the head invites confusion between distinct
hashes; showing only the tail loses the recognisable prefix.

### 5.3 Maps and property data

- **Maps live in a `card-surface` with `border-slate-200`.** No edge-to-edge
  map; the frame signals "this is a controlled view, not the territory."
- **District-coloured polygons.** Each Ugandan district gets a stable hue
  from a deterministic ramp (the existing pilot — Mityana — uses
  `guard-300`). When a polygon needs status, the border carries the status
  colour and the fill carries the district hue.
- **Overlap detection in real time.** When a surveyor draws a new polygon
  and it intersects an existing parcel, the overlap region renders in
  `status-flag` at 30 % opacity. The visual feedback fires *before* the
  submit button — the surveyor learns the rule by drawing.
- **Property data sheet, not pop-up.** Clicking a parcel slides a data
  panel into the right column (citizen) or right rail (officer). Pop-ups
  hide the map; the panel keeps the spatial context.

---

## 6. Accessibility & usability

### 6.1 Contrast

All token combinations are validated against WCAG 2.2 AA. The critical
pairings:

| Foreground       | Background    | Ratio       |
| ---              | ---           | ---         |
| `slate-900`      | `white`       | 17.1 : 1 ✓  |
| `slate-700`      | `white`       | 9.6 : 1 ✓   |
| `slate-500`      | `white`       | 4.8 : 1 ✓   |
| `white`          | `guard-700`   | 7.1 : 1 ✓   |
| `white`          | `guard-950`   | 17.4 : 1 ✓  |
| `seal-700`       | `seal-50`     | 7.3 : 1 ✓   |
| `status-frozen`  | `status-frozen/10` | 4.6 : 1 ✓ |

Light grey on white is not used anywhere as load-bearing text.

### 6.2 Colour-independence

Per WCAG §1.4.1, colour alone never carries meaning. Every status indicator
combines colour + icon + text + `aria-label`. A user with deuteranopia
sees the same information; a screen reader reads the full status.

### 6.3 Focus management

- Visible `:focus-visible` ring on every focusable element (2-px
  `guard-600` outline, 2-px offset). No `outline: none` anywhere.
- Skip-link at the top of every page (`a[href="#main"]`).
- Modal focus traps return focus to the originating element on close.
- Tab order matches reading order on every page.

### 6.4 Mobile and field-officer responsiveness

The officer console is designed laptop-first because that is what the
field officer's MoLHUD-issued device looks like (typically a Lenovo ThinkPad
or HP ProBook). But two adaptations matter:

- **7" tablet support.** The sidebar collapses to a top-bar at `< 1024 px`.
  All touch targets are ≥ 44 × 44 px.
- **Print stylesheet.** The title certificate prints clean A4 — chrome
  hidden, `.print-page` page-break rules, watermark surviving at 5 % opacity
  so even a black-and-white photocopy still shows the pattern (anti-forgery
  property even for offline workflows).

Citizens are designed mobile-first. The public landing and verifier are
both ≤ 180 KB gz on initial load (the budget set by the PWA story), and
both work as a PWA with cached offline verification of the last 50 proofs.

### 6.5 USSD/SMS pathway

Inclusion in this system reaches beyond the GUI. A citizen with a
feature phone verifies a title by:

```
*247*256# → 1 → UG-MIT-T00007/2026
```

The visual design carries this through the GUI — every verifier surface
shows the USSD code beside the QR. The system is not a "PWA with a USSD
fallback"; it is two equal channels into the same verification.

---

## 7. Authority vs ordinary citizen apps — explicit recommendations

The brief specifically asked how LandGuard should feel "more authoritative
than typical citizen apps." The shipped system implements this contrast
through five concrete moves:

1. **Substitute Plex Serif for Inter on institutional headlines.** The
   serif is the single biggest visual cue that a screen is a document
   rather than a feature. Every certificate, every ministry attribution
   band, every page H1 uses serif. Sub-headings stay sans for legibility.
2. **Restrict gold.** Most apps overuse accents. We use gold in three
   places only — certificate seals, on-chain confirmation, and ministry
   attribution. The eye learns to associate gold with "the state has
   signed this."
3. **Restrain rounding and shadow.** Border-radius caps at `0.75 rem`
   (`rounded-xl`). The deepest shadow in the system is on the title
   certificate. No glassmorphism, no backdrop-blur, no glow.
4. **Lead with receipts, not headlines.** Every page that says "this is
   true" shows the hash, transaction, timestamp, or block number that
   makes it true. Where most apps decorate, LandGuard verifies.
5. **Show institutional provenance.** Every public surface sits under a
   ministry attribution band (`guard-950` background, Plex Serif uppercase
   tracking-wide, gold accent) — the same pattern used across `ict.go.ug`,
   `nita.go.ug`, `mlhud.go.ug`. A first-time visitor knows in one glance
   that they are not looking at a startup.

The negative of authority is equally specified — what we **deleted** from
typical app design:

- No dark mode (multiplies every token decision; brief is daylight
  government work).
- No gradients in any direction.
- No emoji in any user-facing surface.
- No exclamation marks in copy.
- No "Welcome back, Sarah! 🎉" patterns.
- No floating action buttons.
- No bottom-sheet patterns or drawer UI.
- No animated illustrations.
- No counters that animate up to a number ("we've processed 1,234,567
  titles!" — government does not do this).
- No social-share buttons on certificate pages.

---

## 8. Anti-patterns (forbidden)

Listed explicitly so they remain rejected in future passes:

- **Dark mode.** Out of scope for the institutional brief.
- **Gradients.** Background, text, or border.
- **Glow / neon / drop-shadows on text.**
- **Glassmorphism / backdrop-blur on chrome.** (The legacy header used
  `backdrop-blur-md`; it has been removed.)
- **`rounded-full` on anything bigger than a 140 px circle.**
- **Custom button styles inline.** All buttons go through `Button.tsx`.
- **Custom status colours.** All status communication goes through
  `StatusPill` and the `status-*` palette.
- **Mock data in production routes.** A page that ships with placeholder
  copy ("Lorem ipsum…") will not pass review.

---

## 9. Provenance

This system was specified in two passes:

1. **Design review pass.** Established the token set, the institutional
   voice, the four-button discipline, and the orange-for-ML / red-for-human
   ethics rule.
2. **Implementation pass.** Shipped the canonical primitives (`Button`,
   `StatusPill`, `HashDisplay`, `CoatOfArmsMark`, `MinistryHeader`,
   `RedactShell`, `RedactToggle`), the three highest-weight surface reskins
   (Merkle visualiser, title certificate, fraud explainer + review queue),
   and the layouts (public + officer console + landing).

The implementation lives at:

- `frontend/tailwind.config.ts` — tokens
- `frontend/src/styles/globals.css` — component classes
- `frontend/src/styles/print.css` — print stylesheet
- `frontend/src/components/common/` — `Button`, `StatusPill`, `HashDisplay`
- `frontend/src/components/layout/` — `MinistryHeader`, `CoatOfArmsMark`,
  `RedactToggle`, `RedactShell`, `DistrictPicker`

Future passes should change tokens before changing components — the tokens
are the contract.
