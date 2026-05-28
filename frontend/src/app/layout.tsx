import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Serif, IBM_Plex_Mono } from "next/font/google";
import "../styles/globals.css";
import "../styles/print.css";
import { Providers } from "@/components/Providers";
import { ServiceWorkerRegistrar } from "@/components/ServiceWorkerRegistrar";

// next/font/google self-hosts at build time — no Google Fonts request at runtime.
const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
  display: "swap",
  preload: true,
});

const plexSerif = IBM_Plex_Serif({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  variable: "--font-plex-serif",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "LandGuard Uganda — Blockchain-Enhanced Land Administration",
    template: "%s · LandGuard Uganda",
  },
  description:
    "Tamper-evident Ugandan land records. Verified by anyone, anywhere — by smartphone, feature phone, or printed certificate.",
  applicationName: "LandGuard Uganda",
  authors: [{ name: "LandGuard Uganda" }],
  keywords: [
    "land registry",
    "blockchain",
    "Uganda",
    "MoLHUD",
    "NIRA",
    "Merkle proof",
    "land titling",
  ],
  manifest: "/manifest.json",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "LandGuard Uganda",
    description: "Tamper-evident land records anchored to a public blockchain.",
    type: "website",
    locale: "en_UG",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#08200d" },
    { media: "(prefers-color-scheme: dark)",  color: "#08200d" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexSerif.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <body className="min-h-screen bg-slate-50 font-sans text-slate-800 antialiased [font-feature-settings:'tnum','lnum']">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-guard-700 focus:px-3 focus:py-2 focus:text-sm focus:text-white"
        >
          Skip to content
        </a>
        <Providers>
          {/* Skip-link target. Each route group ((public)/(app)/etc.) renders
              its own semantic <main>, so this wrapper deliberately does NOT
              use <main> — two <main>s on one page violates HTML5 and breaks
              axe's skip-link audit. tabIndex=-1 makes the target
              programmatically focusable when the skip link is activated. */}
          <div id="main" tabIndex={-1} className="contents">
            {children}
          </div>
          <ServiceWorkerRegistrar />
        </Providers>
      </body>
    </html>
  );
}
