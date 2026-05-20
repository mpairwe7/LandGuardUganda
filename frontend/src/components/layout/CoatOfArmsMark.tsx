/**
 * Coat-of-Arms placeholder mark.
 *
 * For the prototype we ship an abstract heraldic device rather than the
 * actual Ugandan Coat of Arms — using the official emblem requires written
 * authorisation from the Office of the President (see Coat of Arms and
 * Stamps Act, Cap 23). The MOU signing process documented in
 * `docs/moa-templates/MoLHUD-Mityana-Pilot-MOU.md` covers that approval.
 *
 * Visual language: green shield + gold band + crane silhouette stand-in —
 * legible at 22px and below, prints clean in monochrome. Use `variant="light"`
 * on dark surfaces (officer console chrome) so the mark stays readable.
 */
export function CoatOfArmsMark({
  size = 36,
  variant = "default",
  monochrome = false,
}: {
  size?: number;
  variant?: "default" | "light";
  monochrome?: boolean;
}) {
  const isLight = variant === "light";
  const shield = monochrome ? "#08200d" : isLight ? "#16441e" : "#08200d";
  const band   = monochrome ? "#08200d" : "#e8b425";
  const accent = monochrome ? "#ffffff" : "#fdf9ed";
  const edge   = monochrome ? "#08200d" : isLight ? "#e8b425" : "#e8b425";

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 48 48"
      aria-label="Coat of arms (placeholder)"
      role="img"
    >
      {/* Shield */}
      <path
        d="M24 4 L42 9 V24 C42 35 33.5 42.5 24 45 C14.5 42.5 6 35 6 24 V9 Z"
        fill={shield}
        stroke={edge}
        strokeWidth="1.5"
      />
      {/* Gold band */}
      <rect x="6" y="22" width="36" height="4" fill={band} />
      {/* Abstract crane head */}
      <circle cx="24" cy="16" r="3.2" fill={accent} />
      <path d="M24 19 L24 22" stroke={accent} strokeWidth="1.4" />
      {/* Plinth lines */}
      <path
        d="M14 34 H34 M16 38 H32"
        stroke={accent}
        strokeWidth="1.2"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}
