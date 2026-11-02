"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Legend } from "./ui";

export type SeriesDef = {
  key: string;
  label: string;
  color: string;
  /** draw a 10% wash between two keys instead of a line */
  band?: [string, string];
  width?: number;
  hideInLegend?: boolean;
};

type Row = Record<string, number | null | undefined> & { x: number };

export function TimeChart({
  rows,
  series,
  yFormat = (v) => String(v),
  xFormat,
  tipX,
  height = 260,
  refX,
  zeroBased = false,
}: {
  rows: Row[];
  series: SeriesDef[];
  yFormat?: (v: number) => string;
  xFormat: (x: number) => string;
  tipX?: (x: number) => string;
  height?: number;
  refX?: { x: number; label: string };
  zeroBased?: boolean;
}) {
  const legend = series.filter((s) => !s.hideInLegend);
  return (
    <div>
      {legend.length >= 2 && (
        <Legend items={legend.map((s) => ({ label: s.label, color: s.color, kind: s.band ? "band" : "line" }))} />
      )}
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="x"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={xFormat}
              stroke="var(--axis)"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              tickFormatter={yFormat}
              stroke="var(--axis)"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={58}
              domain={zeroBased ? [0, "auto"] : ["auto", "auto"]}
            />
            <Tooltip
              cursor={{ stroke: "var(--axis)" }}
              content={({ active, label, payload }) => {
                if (!active || !payload?.length) return null;
                const row = payload[0].payload as Row;
                return (
                  <div className="card px-3 py-2 text-[12px] shadow-sm">
                    <div className="mb-1 font-medium">{(tipX ?? xFormat)(Number(label))}</div>
                    {series.map((s) => {
                      if (s.band) {
                        const lo = row[s.band[0]];
                        const hi = row[s.band[1]];
                        if (lo == null || hi == null) return null;
                        return (
                          <div key={s.key} className="ink-2">
                            {s.label}: {yFormat(lo)} – {yFormat(hi)}
                          </div>
                        );
                      }
                      const v = row[s.key];
                      if (v == null) return null;
                      return (
                        <div key={s.key} className="flex items-center gap-1.5">
                          <span className="inline-block h-[2px] w-3" style={{ background: s.color }} />
                          <span className="ink-2">{s.label}</span>
                          <span className="ml-auto pl-3 font-medium tabular">{yFormat(v)}</span>
                        </div>
                      );
                    })}
                  </div>
                );
              }}
            />
            {refX && (
              <ReferenceLine
                x={refX.x}
                stroke="var(--axis)"
                label={{ value: refX.label, position: "insideTopLeft", fill: "var(--muted)", fontSize: 11 }}
              />
            )}
            {series.map((s) =>
              s.band ? (
                <Area
                  key={s.key}
                  dataKey={(d: Row) => {
                    const lo = d[s.band![0]];
                    const hi = d[s.band![1]];
                    return lo == null || hi == null ? null : [lo, hi];
                  }}
                  stroke="none"
                  fill={s.color}
                  fillOpacity={0.12}
                  isAnimationActive={false}
                  connectNulls={false}
                  activeDot={false}
                />
              ) : (
                <Line
                  key={s.key}
                  dataKey={s.key}
                  stroke={s.color}
                  strokeWidth={s.width ?? 2}
                  dot={false}
                  activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
                  isAnimationActive={false}
                  connectNulls
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ),
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
