"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

/** "simple" hides the statistics (backtest tables, rule inputs) and leads with plain sentences. */
export type Mode = "simple" | "detailed";

const KEY = "energysignal:view";
const ModeContext = createContext<{ mode: Mode; setMode: (m: Mode) => void }>({ mode: "simple", setMode: () => {} });

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>("simple");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved === "simple" || saved === "detailed") setModeState(saved);
    } catch {
      // private window or blocked storage: stay on the default
    }
  }, []);

  const setMode = (m: Mode) => {
    setModeState(m);
    try {
      localStorage.setItem(KEY, m);
    } catch {}
  };

  return <ModeContext.Provider value={{ mode, setMode }}>{children}</ModeContext.Provider>;
}

export const useViewMode = () => useContext(ModeContext);

export function ViewToggle() {
  const { mode, setMode } = useViewMode();
  return (
    <div
      className="flex rounded-full p-1 text-[12.5px]"
      style={{ background: "var(--wash)" }}
      role="group"
      aria-label="How much detail to show"
    >
      {(["simple", "detailed"] as const).map((m) => (
        <button
          key={m}
          type="button"
          aria-pressed={mode === m}
          onClick={() => setMode(m)}
          className="rounded-full px-3 py-1 capitalize"
          style={{
            background: mode === m ? "var(--ink)" : "transparent",
            color: mode === m ? "var(--surface)" : "var(--ink-2)",
            fontWeight: mode === m ? 600 : 500,
          }}
        >
          {m}
        </button>
      ))}
    </div>
  );
}

/** Renders children only in the given mode. */
export function OnlyIn({ mode, children }: { mode: Mode; children: ReactNode }) {
  return useViewMode().mode === mode ? <>{children}</> : null;
}
