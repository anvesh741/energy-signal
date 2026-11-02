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
    <nav className="flex gap-1 overflow-x-auto text-[14px]" aria-label="Primary">
      {LINKS.map(([href, label]) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className="whitespace-nowrap rounded-lg px-2.5 py-1.5"
            style={{ background: active ? "var(--wash)" : "transparent", fontWeight: active ? 600 : 400 }}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
