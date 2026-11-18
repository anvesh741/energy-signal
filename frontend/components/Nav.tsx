"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  ["/", "Overview"],
  ["/electricity", "Electricity"],
  ["/fuels", "Fuels"],
  ["/forecasts", "Forecasts"],
  ["/sources", "Sources"],
] as const;

export function Nav() {
  const path = usePathname();
  return (
    <nav
      className="flex max-w-full gap-0.5 overflow-x-auto rounded-full p-1 text-[13.5px]"
      style={{ background: "var(--wash)" }}
      aria-label="Primary"
    >
      {LINKS.map(([href, label]) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className="whitespace-nowrap rounded-full px-3.5 py-1.5 transition-colors"
            style={{
              background: active ? "var(--surface)" : "transparent",
              color: active ? "var(--ink)" : "var(--ink-2)",
              fontWeight: active ? 600 : 500,
              boxShadow: active ? "var(--shadow)" : "none",
            }}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
