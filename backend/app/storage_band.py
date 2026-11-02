"""EIA-style 5-year storage band: same ISO week-of-year over the prior five ISO years.

53-week years: if the target is ISO week 53, prior years that have no week 53 use
their week 52 instead (so the band still rests on five years, not one or two).
"""

from datetime import date


def iso_week_key(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return iso.year, iso.week


def week_of_year(d: date) -> int:
    return d.isocalendar().week


def five_year_band(
    weekly: list[tuple[date, float]],
    as_of: date,
    years: int = 5,
) -> dict | None:
    by_year_week = {iso_week_key(d): value for d, value in weekly}
    target_year, target_week = iso_week_key(as_of)
    history: list[float] = []
    used: list[str] = []
    for y in range(target_year - years, target_year):
        week = target_week
        if (y, week) not in by_year_week and week == 53:
            week = 52
        if (y, week) in by_year_week:
            history.append(by_year_week[(y, week)])
            used.append(f"{y}-W{week:02d}")
    if not history:
        return None
    return {
        "week": target_week,
        "as_of": as_of.isoformat(),
        "min": min(history),
        "max": max(history),
        "mean": sum(history) / len(history),
        "n_years": len(history),
        "years_used": used,
        "current": by_year_week.get((target_year, target_week)),
    }


def band_history(weekly: list[tuple[date, float]], last_n: int = 104) -> list[dict]:
    """Band for each of the last `last_n` observed weeks (for charting)."""
    out = []
    for d, value in weekly[-last_n:]:
        b = five_year_band(weekly, d)
        out.append(
            {
                "t": d.isoformat(),
                "value": value,
                "min": b["min"] if b else None,
                "max": b["max"] if b else None,
                "mean": b["mean"] if b else None,
                "n_years": b["n_years"] if b else 0,
            }
        )
    return out
