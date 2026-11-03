"use client";

import { useEffect, useState } from "react";

export const IS_STATIC = process.env.NEXT_PUBLIC_STATIC === "1";
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/** /api/fuels/storage?region=x -> <base>/data/fuels/storage__region_x.json (same mapping as backend/app/export_static.py) */
function resolve(path: string): string {
  if (!IS_STATIC) return path;
  const [route, query] = path.replace(/^\/api\//, "").split("?");
  const name = query ? `${route}__${query.replace(/[&=]/g, "_")}` : route;
  return `${BASE_PATH}/data/${name}.json`;
}

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    setLoading(true);
    fetch(resolve(path))
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
        return r.json();
      })
      .then((d) => !cancelled && (setData(d), setError(null)))
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [path]);

  return { data, error, loading };
}
