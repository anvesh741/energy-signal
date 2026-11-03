import type { Metadata } from "next";
import Link from "next/link";

import { Nav } from "@/components/Nav";
import { SnapshotNote } from "@/components/SnapshotNote";

import "./globals.css";

export const metadata: Metadata = {
  title: "EnergySignal",
  description: "Electricity demand and generation, oil and gas prices, with honest cadence-aware statistical forecasts.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header style={{ borderBottom: "1px solid var(--border)", background: "var(--surface)" }}>
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-2.5">
            <Link href="/" className="text-[15px] font-semibold">
              EnergySignal
            </Link>
            <Nav />
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-8 text-[12px] muted">
          Data: U.S. Energy Information Administration · Ember (CC BY 4.0) · World Bank Pink Sheet (CC BY 4.0). Not
          trading advice. See <Link href="/sources" className="underline">Sources</Link> for lags and licenses.
          <SnapshotNote />
        </footer>
      </body>
    </html>
  );
}
