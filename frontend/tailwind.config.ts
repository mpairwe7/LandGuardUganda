import type { Config } from "tailwindcss";

/**
 * LandGuard Uganda — Design System Tokens
 *
 * Aligned with the visual identity of Ugandan government digital services
 * (deep institutional green, gold-as-seal, IBM Plex typography). See
 * docs/DESIGN_SYSTEM.md for the rationale behind every token.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Primary — Uganda Forest Green. Darker than commercial "green".
        guard: {
          50:  "#f0f8f1",
          100: "#d8ecd9",
          200: "#b3d9b6",
          300: "#82bf87",
          400: "#4f9e57",
          500: "#2f8138",
          600: "#20672a",
          700: "#1a5223",
          800: "#16441e",
          900: "#133819",
          950: "#08200d",
        },
        // Accent — Uganda Gold. Reserved for seals, certificate marks, anchored pills.
        seal: {
          50:  "#fdf9ed",
          100: "#faf0ca",
          200: "#f5e08e",
          300: "#efc94e",
          400: "#e8b425",
          500: "#d49a18",
          600: "#b67a14",
          700: "#925b13",
          800: "#784816",
          900: "#663d18",
        },
        // Semantic colours — always paired with an icon in the UI.
        status: {
          verified: "#15803d",
          pending:  "#b45309",
          flag:     "#c2410c",
          frozen:   "#b91c1c",
          chain:    "#1e40af",
          neutral:  "#475569",
        },
      },
      fontFamily: {
        sans:  ["var(--font-plex-sans)",  "system-ui", "sans-serif"],
        serif: ["var(--font-plex-serif)", "Georgia",   "serif"],
        mono:  ["var(--font-plex-mono)",  "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        caption: ["0.75rem",  { lineHeight: "1rem",   letterSpacing: "0.01em" }],
        xs:      ["0.8125rem",{ lineHeight: "1.125rem" }],
        sm:      ["0.875rem", { lineHeight: "1.25rem" }],
        base:    ["1rem",     { lineHeight: "1.5rem" }],
        lg:      ["1.125rem", { lineHeight: "1.75rem" }],
        xl:      ["1.25rem",  { lineHeight: "1.75rem", letterSpacing: "-0.005em" }],
        "2xl":   ["1.5rem",   { lineHeight: "2rem",    letterSpacing: "-0.01em" }],
        "3xl":   ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.015em" }],
        "4xl":   ["2.25rem",  { lineHeight: "2.5rem",  letterSpacing: "-0.02em" }],
        display: ["3rem",     { lineHeight: "3.5rem",  letterSpacing: "-0.025em" }],
      },
      borderRadius: {
        // Government formal — restrained rounding.
        sm: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
      },
      boxShadow: {
        // No glamorous shadows. Subtle elevation only.
        card:     "0 1px 2px 0 rgb(15 23 42 / 0.04)",
        elevated: "0 1px 3px 0 rgb(15 23 42 / 0.08), 0 1px 2px -1px rgb(15 23 42 / 0.04)",
        document: "0 8px 24px -8px rgb(15 23 42 / 0.12), 0 2px 6px -2px rgb(15 23 42 / 0.06)",
      },
      animation: {
        "pulse-slow": "pulse 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in":    "fade-in 320ms ease-out",
        "slide-up":   "slide-up 240ms ease-out",
      },
      keyframes: {
        "fade-in":  { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "slide-up": { from: { opacity: "0", transform: "translateY(16px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      maxWidth: {
        // Anchors for citizen vs officer canvases.
        citizen: "896px",
        officer: "1280px",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
