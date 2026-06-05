import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Fraunces, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

// Distinctive type system (per the frontend-design skill — no Inter/Roboto/Arial):
//  · Fraunces  — characterful serif, the wordmark + the insight prose
//  · Plex Sans — refined technical body/UI
//  · Plex Mono — the SQL slab + tabular data (the instrument's voice)
// Self-hosted by next/font at build time; no runtime Google calls.
const fraunces = Fraunces({
  subsets: ["latin"],
  // Variable font: keep the optical-sizing axis and the full weight range (no
  // explicit `weight` — next/font forbids combining `weight` with `axes`). CSS
  // then uses font-weight 400–600 freely.
  axes: ["opsz"],
  variable: "--font-display",
  display: "swap",
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "NIXUS SQL",
  description: "Ask in plain language. See the SQL it ran.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${plexSans.variable} ${plexMono.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
