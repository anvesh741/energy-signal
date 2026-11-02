import type { ReactNode } from "react";

export function Card({
  title,
  subtitle,
  footer,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  footer?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card p-4 sm:p-5 min-w-0 ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold leading-snug">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[13px] ink-2">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap gap-1.5">{actions}</div>}
        </header>
      )}
      {children}
      {footer && <footer className="mt-3 text-[12px] muted">{footer}</footer>}
    </section>
  );
}

export function Stat({
  label,
  value,
  unit,
  delta,
  note,
}: {
  label: string;
  value: string;
  unit?: string;
  delta?: { text: string; dir: "up" | "down" | "flat"; vs: string } | null;
  note?: ReactNode;
}) {
  return (
    <div className="card p-4 min-w-0">
      <div className="text-[13px] ink-2">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-[28px] font-semibold leading-none">{value}</span>
        {unit && <span className="text-[13px] muted">{unit}</span>}
      </div>
      {delta && (
        <div className="mt-1.5 text-[13px] ink-2">
          <span aria-hidden>{delta.dir === "up" ? "▲" : delta.dir === "down" ? "▼" : "■"}</span>{" "}
          <span className="font-medium" style={{ color: "var(--ink)" }}>
            {delta.text}
          </span>{" "}
          {delta.vs}
        </div>
      )}
      {note && <div className="mt-2 text-[12px] muted leading-snug">{note}</div>}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string; kind?: "line" | "band" | "box" | "hatch" }[] }) {
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] ink-2" aria-label="Legend">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-1.5">
          <Swatch color={it.color} kind={it.kind ?? "line"} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

export function Swatch({ color, kind }: { color: string; kind: "line" | "band" | "box" | "hatch" }) {
  if (kind === "line") return <span className="inline-block h-[2px] w-4 rounded" style={{ background: color }} />;
  if (kind === "band")
    return <span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: color, opacity: 0.18 }} />;
  if (kind === "hatch")
    return (
      <span
        className="inline-block h-2.5 w-2.5 rounded-sm"
        style={{ background: `repeating-linear-gradient(45deg, ${color} 0 2px, transparent 2px 4px)` }}
      />
    );
  return <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />;
}

export function DemoBanner({ show }: { show?: boolean }) {
  if (!show) return null;
  return (
    <div className="card mb-4 px-4 py-2.5 text-[13px]" role="status" style={{ borderColor: "var(--warning)" }}>
      <strong>⚠ Demo data.</strong>{" "}
      <span className="ink-2">
        These are synthetic values from <code>python -m app.demo_seed</code>, not real prices or demand. Add EIA
        and Ember keys to <code>.env</code> and run the scheduler to replace them.
      </span>
    </div>
  );
}

export function Loading({ error }: { error?: string | null }) {
  return (
    <div className="card p-6 text-[13px] ink-2">
      {error ? (
        <>
          <strong>Could not reach the API.</strong> Is the backend running on :8000? <span className="muted">{error}</span>
        </>
      ) : (
        "Loading…"
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-10 text-center text-[13px] muted">{children}</div>;
}

export function TableView({
  columns,
  rows,
  summary = "Show data table",
}: {
  columns: string[];
  rows: (string | number)[][];
  summary?: string;
}) {
  return (
    <details className="mt-2">
      <summary>{summary}</summary>
      <div className="mt-2 max-h-72 overflow-auto">
        <table className="data">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j}>{c}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function PageTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-5">
      <h1 className="text-[22px] font-semibold">{title}</h1>
      {children && <p className="mt-1 max-w-3xl text-[14px] ink-2">{children}</p>}
    </div>
  );
}
