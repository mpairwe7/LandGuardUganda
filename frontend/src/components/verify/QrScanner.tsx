"use client";

import { Scanner } from "@yudiel/react-qr-scanner";

interface Props {
  onResult: (titleNo: string) => void;
}

/**
 * Extracts a title_no from a scanned QR. We accept multiple encodings:
 *   - raw UPI/title string (e.g. "UG-MIT-T00007/2026")
 *   - https://landguard.ug/verify?title=UG-MIT-T00007/2026
 *   - JSON {"title_no":"UG-MIT-T00007/2026","batch_id":"...","leaf":"...","siblings":[...]}
 */
function extractTitle(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  // URL?
  try {
    const url = new URL(trimmed);
    const t = url.searchParams.get("title");
    if (t) return t.toUpperCase();
  } catch {
    /* not a URL */
  }
  // JSON?
  if (trimmed.startsWith("{")) {
    try {
      const obj = JSON.parse(trimmed) as { title_no?: string };
      if (obj.title_no) return obj.title_no.toUpperCase();
    } catch {
      /* not JSON */
    }
  }
  // Looks like a UPI/title?
  if (/^UG-[A-Z]{3}-T?\d{5,6}\/\d{4}$/.test(trimmed.toUpperCase())) {
    return trimmed.toUpperCase();
  }
  return null;
}

export function QrScanner({ onResult }: Props) {
  return (
    <div className="overflow-hidden rounded-md border border-slate-200 bg-slate-50">
      <Scanner
        constraints={{ facingMode: "environment" }}
        formats={["qr_code"]}
        onScan={(results) => {
          if (!results.length) return;
          const text = results[0]?.rawValue;
          if (!text) return;
          const parsed = extractTitle(text);
          if (parsed) onResult(parsed);
        }}
        onError={() => undefined}
        styles={{ container: { aspectRatio: "1/1", maxWidth: 400 } }}
      />
    </div>
  );
}
