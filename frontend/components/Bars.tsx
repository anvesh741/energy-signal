"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Legend } from "./ui";

export type BarRow = { label: string; [k: string]: string | number | boolean | null };

/** Columns from one baseline, <=24px, 4px rounded data-end. `hatched(row)` marks partial bars. */
export function Columns({
  rows,
  keys,
  yFormat,
  height = 220,
  hatched,
  tooltip,
}: {
  rows: BarRow[];
  keys: { key: string; label: string; color: string }[];
  yFormat: (v: number) => string;
  height?: number;
  hatched?: (r: BarRow) => boolean;
  tooltip: (r: BarRow) => React.ReactNode;
}) {
  const stacked = keys.length > 1;
  return (
    <div>
      {stacked && <Legend items={keys.map((k) => ({ label: k.label, color: k.color, kind: "box" }))} />}
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 6, right: 12, bottom: 0, left: 0 }} barCategoryGap="20%">
            <defs>
              <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill="var(--wash)" />
                <line x1="0" y1="0" x2="0" y2="6" stroke="var(--muted)" strokeWidth="2" />
              </pattern>
            </defs>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="var(--axis)"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              tickLine={false}
              minTickGap={16}
            />
            <YAxis
              tickFormatter={yFormat}
              stroke="var(--axis)"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={58}
            />
            <Tooltip
              cursor={{ fill: "var(--wash)", opacity: 0.5 }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <div className="card px-3 py-2 text-[12px] shadow-sm">{tooltip(payload[0].payload as BarRow)}</div>
                ) : null
              }
            />
            {keys.map((k, i) => (
              <Bar
                key={k.key}
                dataKey={k.key}
                stackId={stacked ? "s" : undefined}
                fill={k.color}
                maxBarSize={24}
                radius={!stacked || i === keys.length - 1 ? [4, 4, 0, 0] : 0}
                stroke={stacked ? "var(--surface)" : undefined}
                strokeWidth={stacked ? 1 : 0}
                isAnimationActive={false}
              >
                {!stacked &&
                  rows.map((r, j) => <Cell key={j} fill={hatched?.(r) ? "url(#hatch)" : k.color} />)}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
