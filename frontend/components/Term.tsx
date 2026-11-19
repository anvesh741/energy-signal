import type { ReactNode } from "react";

import { GLOSSARY } from "@/lib/glossary";

/** A dotted-underlined word with its definition on hover or keyboard focus. */
export function Term({ k, children }: { k: keyof typeof GLOSSARY | string; children?: ReactNode }) {
  const tip = GLOSSARY[k];
  if (!tip) return <>{children ?? k}</>;
  return (
    <span className="term" tabIndex={0} data-tip={tip}>
      {children ?? k}
    </span>
  );
}
