export const US48_TZ = "America/New_York";

export function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function compact(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: digits }).format(v);
}

export function pct(v: number | null | undefined, digits = 1, signed = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${signed && v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

/** "Oct 28" — the data date, in UTC unless a tz is given (EIA daily dates are UTC midnights). */
export function day(iso: string | number | null | undefined, tz = "UTC", withYear = false): string {
  if (iso === null || iso === undefined) return "—";
  const d = typeof iso === "number" ? new Date(iso) : new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(withYear ? { year: "numeric" } : {}),
    timeZone: tz,
  });
}

export function dateTime(iso: string | number | null | undefined, tz = US48_TZ): string {
  if (iso === null || iso === undefined) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    timeZone: tz,
    timeZoneName: "short",
  });
}

export function lag(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "—";
  if (hours < 0) return "ahead (forecast)";
  if (hours < 1) return "<1 h";
  if (hours < 48) return `${Math.round(hours)} h`;
  return `${(hours / 24).toFixed(1)} d`;
}

export const ms = (iso: string) => new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso).getTime();
