"use client";

import { useViewMode } from "@/components/ViewMode";
import { insightMeaning } from "@/lib/explain";
import { day } from "@/lib/format";
import type { Insight } from "@/lib/types";

export function InsightInputs({ inputs }: { inputs: string }) {
  const { mode } = useViewMode();
  if (mode === "simple") return null;
  let parsed: Record<string, unknown> = {};
  try {
    parsed = JSON.parse(inputs);
  } catch {
    return null;
  }
  const entries = Object.entries(parsed).filter(([, v]) => typeof v !== "object");
  return (
    <details className="mt-1.5">
      <summary>Inputs{parsed.window ? ` · window: ${parsed.window}` : ""}</summary>
      <table className="data mt-1">
        <tbody>
          {entries.map(([k, v]) => (
            <tr key={k}>
              <td className="ink-2">{k}</td>
              <td>{typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: 4 }) : String(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

const RULE_LABEL: Record<string, string> = {
  demand_week: "Demand week",
  price_move: "Price move",
  storage_band: "Storage band",
};

export function InsightList({ items }: { items: Insight[] }) {
  if (!items.length) return <p className="text-[13px] muted">No insights yet — they fire only on new observations.</p>;
  return (
    <ul className="divide-y" style={{ borderColor: "var(--grid)" }}>
      {items.map((i) => (
        <li key={`${i.rule_id}-${i.series_id}`} className="py-3.5" style={{ borderColor: "var(--grid)" }}>
          <div className="flex items-start gap-3">
            <span
              className="mono mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold"
              style={{
                background: i.rank <= 2 ? "var(--signal-soft)" : "var(--wash)",
                color: i.rank <= 2 ? "var(--signal-ink)" : "var(--ink-2)",
              }}
              title={`Rank ${i.rank} (lower = more notable)`}
            >
              {i.rank}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[14px] font-medium leading-snug">{i.headline}</div>
              <div className="mt-1 text-[13px] leading-relaxed ink-2">{insightMeaning(i)}</div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <span className="chip">{RULE_LABEL[i.rule_id] ?? i.rule_id}</span>
                {i.state && i.state !== "normal" && i.state !== "inside" && (
                  <span className="chip signal">{i.state}</span>
                )}
                <span className="mono text-[11.5px] muted">
                  as of {day(i.as_of, i.rule_id === "demand_week" ? "America/New_York" : "UTC")}
                </span>
              </div>
            </div>
          </div>
          <div className="pl-9">
            <InsightInputs inputs={i.inputs} />
          </div>
        </li>
      ))}
    </ul>
  );
}
