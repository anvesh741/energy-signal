from datetime import date, timedelta

from app.storage_band import band_history, five_year_band, week_of_year


def _fridays(start: date, end: date, value=lambda d: 3000.0 + week_of_year(d)):
    d = start + timedelta(days=(4 - start.weekday()) % 7)
    out = []
    while d < end:
        out.append((d, value(d)))
        d += timedelta(days=7)
    return out


def test_band_uses_same_week_of_prior_five_years():
    weekly = _fridays(date(2017, 1, 1), date(2024, 6, 1))
    band = five_year_band(weekly, date(2024, 3, 8))
    assert band["n_years"] == 5
    assert band["years_used"] == [f"{y}-W10" for y in range(2019, 2024)]
    assert band["min"] == band["max"] == 3010.0
    assert band["current"] == 3010.0


def test_week_53_falls_back_to_week_52_in_years_without_it():
    weekly = _fridays(date(2015, 1, 1), date(2021, 2, 1))
    as_of = date(2020, 12, 31)  # ISO 2020-W53
    assert week_of_year(as_of) == 53
    band = five_year_band(weekly, as_of)
    assert band["n_years"] == 5
    assert band["years_used"] == ["2015-W53", "2016-W52", "2017-W52", "2018-W52", "2019-W52"]


def test_week_after_53_week_year_is_week_1():
    weekly = _fridays(date(2015, 1, 1), date(2021, 2, 1))
    band = five_year_band(weekly, date(2021, 1, 8))  # ISO 2021-W01
    assert band["week"] == 1 and band["n_years"] == 5


def test_band_history_length():
    weekly = _fridays(date(2017, 1, 1), date(2024, 6, 1))
    assert len(band_history(weekly, 52)) == 52
