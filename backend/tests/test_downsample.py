from datetime import datetime, timedelta, timezone

from app.downsample import min_max_buckets


def test_min_max_keeps_the_peak_and_trough():
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    pts = [(t0 + timedelta(hours=i), 100.0) for i in range(5000)]
    pts[1234] = (pts[1234][0], 999.0)
    pts[4321] = (pts[4321][0], 1.0)
    out = min_max_buckets(pts, 200)
    assert len(out) <= 200
    assert max(p["max"] for p in out) == 999.0
    assert min(p["min"] for p in out) == 1.0


def test_small_series_passes_through():
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert len(min_max_buckets([(t0, 1.0), (t0 + timedelta(hours=1), 2.0)], 800)) == 2
