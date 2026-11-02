import math
import random
from datetime import datetime, timedelta, timezone

from app.eval import backtest, mase_scale, origin_indices
from app.forecast import ForecastSpec, naive

T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _walk(n, vol=0.02, seed=1):
    rng = random.Random(seed)
    v, out = 100.0, []
    for i in range(n):
        v *= math.exp(rng.gauss(0, vol))
        out.append((T0 + timedelta(days=i), v))
    return out


def test_origins_leave_horizon_and_respect_min_train():
    origins = origin_indices(50, min_train=10, horizon=7, stride=7)
    assert origins == sorted(origins)
    assert all(o >= 9 and o + 7 < 50 for o in origins)


def test_origins_empty_when_too_short_and_capped():
    assert origin_indices(5, min_train=10, horizon=7) == []
    capped = origin_indices(100, min_train=10, horizon=1, max_origins=5)
    assert capped == [94, 95, 96, 97, 98]


def test_backtest_never_sees_the_future():
    hist = _walk(120)

    def spy(train, targets, steps):
        assert all(t > train[-1][0] for t in targets)
        assert len(train) + max(steps) - 1 < len(hist)
        return [train[-1][1]] * len(targets)

    spec = ForecastSpec("x", "daily", {"spy": spy}, [1, 5], {"1d": [1], "1w": [5]}, None, lambda t, s: t, min_train=30)
    acc = backtest(spec, hist, "spy")
    assert acc["1d"]["origins"]


def test_naive_band_coverage_is_close_to_nominal_on_a_random_walk():
    hist = _walk(1500, seed=7)
    spec = ForecastSpec("x", "daily", {"naive": naive}, [1, 5], {"1d": [1], "1w": [5]}, None, lambda t, s: t,
                        min_train=60, max_origins=2000)
    acc = backtest(spec, hist, "naive")
    for bucket in ("1d", "1w"):
        coverage = acc[bucket]["hits"] / len(acc[bucket]["abs"])
        assert 0.74 < coverage < 0.86, (bucket, coverage)


def test_mase_scale():
    assert mase_scale([1, 2, 4, 7], None) == 2.0
    assert mase_scale([1, 5, 1, 5, 1, 5], 2) is None  # zero seasonal variation
