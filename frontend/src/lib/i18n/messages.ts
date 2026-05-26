// Stub i18n catalogue. Two locales are wired:
//
//   en  — English, the source language (authoritative).
//   lg  — Luganda — best-effort, needs native-speaker review before
//         the Mityana pilot. The intent of shipping this stub now is
//         to *demonstrate the architecture* and respect the
//         linguistic posture stated in docs/STANDARDS_ALIGNMENT.md,
//         not to deliver a finished translation.
//
// The catalogue is intentionally narrow: only the citizen-facing
// public verifier (`/verify`) is translated for the showcase, plus a
// few global UI affordances (locale switch label, USSD hint shared
// with the landing page). Other surfaces will follow once a Luganda
// linguist is engaged.

export type Locale = "en" | "lg";

export const LOCALES: readonly Locale[] = ["en", "lg"] as const;
export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_LABEL: Record<Locale, string> = {
  en: "English",
  lg: "Luganda",
};

export interface Messages {
  "locale.switch_to": string;

  "verify.eyebrow": string;
  "verify.title": string;
  "verify.subtitle": string;
  "verify.input.placeholder": string;
  "verify.input.label": string;
  "verify.button.verify": string;
  "verify.button.scan": string;
  "verify.button.scan_close": string;
  "verify.ussd_hint.before": string;
  "verify.ussd_hint.after": string;

  "verify.result.verified.title": string;
  "verify.result.verified.confirmed": string;
  "verify.result.verified.anchored": string;
  "verify.result.verified.body": string;

  "verify.result.pending.title": string;
  "verify.result.pending.label": string;
  "verify.result.pending.body": string;

  "verify.result.failed.title": string;
  "verify.result.failed.label": string;
  "verify.result.notfound.body": string;

  "verify.error.title": string;
  "verify.error.body_default": string;

  "verify.receipt.title": string;
  "verify.receipt.batch": string;
  "verify.receipt.chain": string;
  "verify.receipt.block": string;
}

const en: Messages = {
  "locale.switch_to": "Switch language",

  "verify.eyebrow": "Public verifier",
  "verify.title": "Verify a land title",
  "verify.subtitle":
    "Paste a title number or scan its QR code. The system computes a Merkle inclusion proof, recalls it from the off-chain ledger, and asks the on-chain contract to confirm. No LandGuard credentials needed — anyone can do this.",
  "verify.input.placeholder": "UG-MIT-T00007/2026",
  "verify.input.label": "Title number",
  "verify.button.verify": "Verify",
  "verify.button.scan": "Scan QR",
  "verify.button.scan_close": "Close scanner",
  "verify.ussd_hint.before": "No smartphone? Dial ",
  "verify.ussd_hint.after": " from any phone to verify by USSD.",

  "verify.result.verified.title": "Title verified",
  "verify.result.verified.confirmed": "Confirmed on chain",
  "verify.result.verified.anchored": "Anchored",
  "verify.result.verified.body":
    "This title is recorded in a district ledger and anchored to a public blockchain. Any modification to the certificate would break the Merkle proof shown below.",

  "verify.result.pending.title": "Anchor pending",
  "verify.result.pending.label": "Awaiting anchor",
  "verify.result.pending.body":
    "This title exists in the off-chain ledger but its anchor batch is still pending. Re-check in a few minutes — your title remains legally valid in the meantime.",

  "verify.result.failed.title": "Could not verify",
  "verify.result.failed.label": "Verification failed",
  "verify.result.notfound.body":
    "We could not find this title in any district ledger. Check the title number for transcription errors, or contact your District Land Office.",

  "verify.error.title": "Verification failed",
  "verify.error.body_default":
    "We could not reach the verifier. Try again in a moment.",

  "verify.receipt.title": "Title",
  "verify.receipt.batch": "Batch",
  "verify.receipt.chain": "Chain",
  "verify.receipt.block": "Block",
};

// Luganda — best-effort working draft. Reviewed against the spec in
// docs/STANDARDS_ALIGNMENT.md but NOT yet by a Luganda linguist.
// Track translation polish in issue #i18n-lg-review (to be opened).
const lg: Messages = {
  "locale.switch_to": "Kyusa olulimi",

  "verify.eyebrow": "Okukakasa kw’abantu bonna",
  "verify.title": "Kakasa ekiwandiiko ky’ettaka",
  "verify.subtitle":
    "Yingiza ennamba y’ekiwandiiko oba scan akabonero ka QR kakyo. Sisitemu ekuba Merkle inclusion proof, ekiggya mu ledger ey’ekitundu, era esaba ssente ya kondulakiti okukakasa. Tewetaagisa kayungo ka LandGuard — buli muntu asobola.",
  "verify.input.placeholder": "UG-MIT-T00007/2026",
  "verify.input.label": "Ennamba y’ekiwandiiko",
  "verify.button.verify": "Kakasa",
  "verify.button.scan": "Scan QR",
  "verify.button.scan_close": "Ggalawo scanner",
  "verify.ussd_hint.before": "Tolinaayo simu ennambi? Kuba ",
  "verify.ussd_hint.after": " okuva ku simu yonna okukakasa nga oyita ku USSD.",

  "verify.result.verified.title": "Ekiwandiiko kikakasibbwa",
  "verify.result.verified.confirmed": "Kikakasibbwa ku chain",
  "verify.result.verified.anchored": "Kinywezeddwa",
  "verify.result.verified.body":
    "Ekiwandiiko kino kiwandiikiddwa mu ledger ey’ekitundu era kinywezeddwa ku blockchain ey’abantu bonna. Buli nkyukakyuka ku ssatifikeeti yandiyabudde Merkle proof eraga waggulu.",

  "verify.result.pending.title": "Anchor ekyali",
  "verify.result.pending.label": "Esuubira anchor",
  "verify.result.pending.body":
    "Ekiwandiiko kino kiriwo mu ledger naye batch yaakyo erindirira okunywezebwa. Komawo oluvannyuma lw’edakika ntono — ekiwandiiko kyo kikyali ekikola mu mateeka.",

  "verify.result.failed.title": "Tetwasobodde kukakasa",
  "verify.result.failed.label": "Okukakasa kugaanidde",
  "verify.result.notfound.body":
    "Tetwasobodde kuzuula kiwandiiko kino mu ledger yonna. Kebera ennamba y’ekiwandiiko oba okwete ku District Land Office.",

  "verify.error.title": "Okukakasa kugaanidde",
  "verify.error.body_default":
    "Tetwasobodde kutuuka ku verifier. Gezaako nate oluvannyuma lw’edakika ntono.",

  "verify.receipt.title": "Ekiwandiiko",
  "verify.receipt.batch": "Batch",
  "verify.receipt.chain": "Chain",
  "verify.receipt.block": "Block",
};

export const messages: Record<Locale, Messages> = { en, lg };
