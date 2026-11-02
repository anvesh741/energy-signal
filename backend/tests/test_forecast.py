import math
from datetime import datetime, timedelta, timezone

from app.forecast import band, fourier_ar, naive, rolling_log_errors, seasonal_mean, seasonal_naive

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def _daily(values):
    return [(T0 + i * DAY, float(v)) for i, v in enumerate(values)]


def test_seasonal_naive_uses_the_matching_weekday_for_every_horizon():
    hist = _daily(range(14))  # last value 13 at day 13
    targets = [hist[-1][0] + s * DAY for s in range(1, 10)]
    points = seasonal_naive(7 * DAY)(hist, targets, list(range(1, 10)))
    # h=1..7 -> days 7..13, h=8,9 -> days 7,8 (two seasons back)
    assert points == [7, 8, 9, 10, 11, 12, 13, 7, 8]


def test_seasonal_naive_skips_a_missing_day():
    hist = [p for p in _daily(range(21)) if p[0] != T0 + 14 * DAY]  # partial day excluded
    (point,) = seasonal_naive(7 * DAY)(hist, [T0 + 21 * DAY], [1])
    assert point == 7.0


def test_seasonal_mean_of_last_four_weekdays():
    hist = _daily(range(35))
    (point,) = seasonal_mean(7 * DAY, 4)(hist, [T0 + 35 * DAY], [1])
    assert point == (28 + 21 + 14 + 7) / 4


def test_naive_band_equals_h_step_log_return_quantiles():
    values = [100 * math.exp(0.01 * math.sin(i) + 0.001 * i) for i in range(300)]
    hist = _daily(values)
    errs = rolling_log_errors(hist, naive, [5], min_train=30, stride=1, max_origins=10_000)
    returns = [math.log(values[i + 5] / values[i]) for i in range(29, len(values) - 5)]
    assert sorted(errs[5]) == sorted(returns)
    lo, hi = band(values[-1], errs[5])
    assert lo < values[-1] < hi


def test_band_needs_enough_samples():
    assert band(100.0, [0.01] * 5) == (None, None)


def test_fourier_tracks_a_daily_cycle():
    hours = [(T0 + timedelta(hours=i), 1000 + 100 * math.sin(2 * math.pi * i / 24)) for i in range(24 * 28)]
    last = hours[-1][0]
    targets = [last + timedelta(hours=h) for h in range(1, 25)]
    preds = fourier_ar("UTC")(hours, targets, list(range(1, 25)))
    truth = [1000 + 100 * math.sin(2 * math.pi * (24 * 28 - 1 + h) / 24) for h in range(1, 25)]
    assert max(abs(p - t) for p, t in zip(preds, truth)) < 5
