import { day } from "@/lib/format";
import type { Insight } from "@/lib/types";

export function InsightInputs({ inputs }: { inputs: string }) {
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

export function InsightList({ items }: { items: Insight[] }) {
  if (!items.length) return <p className="text-[13px] muted">No insights yet — they fire only on new observations.</p>;
  return (
    <ul className="divide-y" style={{ borderColor: "var(--grid)" }}>
      {items.map((i) => (
        <li key={`${i.rule_id}-${i.series_id}`} className="py-2.5" style={{ borderColor: "var(--grid)" }}>
          <div className="text-[14px]">{i.headline}</div>
          <div className="mt-0.5 text-[12px] muted">as of {day(i.as_of, i.rule_id === "demand_week" ? "America/New_York" : "UTC")}</div>
          <InsightInputs inputs={i.inputs} />
        </li>
      ))}
    </ul>
  );
}
