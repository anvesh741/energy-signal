"""Server-side downsampling that keeps peaks: min and max per bucket, never mean-only."""

from datetime import datetime


def min_max_buckets(points: list[tuple[datetime, float]], max_points: int = 800) -> list[dict]:
    """Split the series into ~max_points/2 equal-count buckets; emit each bucket's min and max
    (plus its last value for a line), so daily peaks and troughs survive."""
    if not points:
        return []
    points = sorted(points, key=lambda p: p[0])
    if len(points) <= max_points:
        return [{"t": t.isoformat(), "min": v, "max": v, "value": v} for t, v in points]
    n_buckets = max(1, max_points // 2)
    size = len(points) / n_buckets
    out = []
    for b in range(n_buckets):
        chunk = points[int(b * size) : int((b + 1) * size)]
        if not chunk:
            continue
        values = [v for _, v in chunk]
        out.append(
            {
                "t": chunk[-1][0].isoformat(),
                "min": min(values),
                "max": max(values),
                "value": chunk[-1][1],
            }
        )
    return out
