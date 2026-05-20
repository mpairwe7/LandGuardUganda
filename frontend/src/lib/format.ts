export function formatUgx(amount: number | null | undefined): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat("en-UG", {
    style: "currency",
    currency: "UGX",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatHectares(ha: number | null | undefined): string {
  if (ha == null) return "—";
  return `${ha.toFixed(2)} ha`;
}

export function shortHash(hex: string | null | undefined, head = 6, tail = 4): string {
  if (!hex) return "—";
  const stripped = hex.startsWith("0x") ? hex.slice(2) : hex;
  if (stripped.length <= head + tail) return hex;
  const prefix = hex.startsWith("0x") ? "0x" : "";
  return `${prefix}${stripped.slice(0, head)}…${stripped.slice(-tail)}`;
}

export function formatTs(ts: number | null | undefined): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("en-UG", { dateStyle: "medium", timeStyle: "short" });
}

export function tenureLabel(t: string): string {
  switch (t) {
    case "MAILO":
      return "Mailo";
    case "FREEHOLD":
      return "Freehold";
    case "LEASEHOLD":
      return "Leasehold";
    case "CUSTOMARY":
      return "Customary";
    default:
      return t;
  }
}
