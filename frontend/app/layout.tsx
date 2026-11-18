import type { Metadata } from "next";
import { JetBrains_Mono, Schibsted_Grotesk } from "next/font/google";
import Link from "next/link";

import { Nav } from "@/components/Nav";
import { SnapshotNote } from "@/components/SnapshotNote";

import "./globals.css";

const sans = Schibsted_Grotesk({ subsets: ["latin"], variable: "--font-schibsted", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains", display: "swap" });

export const metadata: Metadata = {
  title: "EnergySignal",
  description: "Electricity demand and generation, oil and gas prices, with honest cadence-aware statistical forecasts.",
};

/** A grid pulse: the brand mark. */
function Mark() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
      <rect width="26" height="26" rx="7" fill="var(--ink)" />
      <path
        d="M4 14h4.5l2-5 3.5 10 2.5-7 1.5 2H22"
        fill="none"
        stroke="var(--signal)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <header
          className="sticky top-0 z-20 backdrop-blur"
          style={{
            borderBottom: "1px solid var(--border)",
            background: "color-mix(in srgb, var(--surface) 82%, transparent)",
          }}
        >
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <Link href="/" className="flex items-center gap-2.5">
              <Mark />
              <span className="text-[16px] font-bold tracking-tight">
                Energy<span style={{ color: "var(--signal)" }}>Signal</span>
              </span>
            </Link>
            <Nav />
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer style={{ borderTop: "1px solid var(--border)", background: "var(--surface)" }}>
          <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 text-[12.5px] sm:grid-cols-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Mark />
                <span className="font-bold">EnergySignal</span>
              </div>
              <p className="mt-2 ink-2">
                U.S. and global energy data, refreshed daily, with forecasts that show how accurate they really are.
              </p>
            </div>
            <div className="min-w-0">
              <div className="eyebrow mb-2">Data</div>
              <p className="ink-2">
                U.S. Energy Information Administration · Ember (CC BY 4.0) · World Bank Pink Sheet (CC BY 4.0). See{" "}
                <Link href="/sources" className="underline">
                  Sources
                </Link>{" "}
                for lags and licenses.
              </p>
            </div>
            <div className="min-w-0">
              <div className="eyebrow mb-2">Status</div>
              <p className="ink-2">
                Not trading advice.
                <SnapshotNote />
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
