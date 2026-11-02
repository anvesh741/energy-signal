from datetime import datetime, timedelta, timezone

from app.insights import band_state, ordinal, price_state, should_emit
from app.models import Insight

AS_OF = datetime(2024, 10, 28, tzinfo=timezone.utc)


def _seed(session):
    session.add(
        Insight(
            rule_id="price_move", series_id="eia-wti", rank=1, issued_at=AS_OF,
            as_of_ts=AS_OF, cooldown_until=AS_OF + timedelta(hours=18), headline="x",
        )
    )
    session.commit()


def test_does_not_fire_without_new_observation(session):
    _seed(session)
    assert not should_emit(session, "price_move", "eia-wti", AS_OF, now=AS_OF + timedelta(days=3))


def test_fires_on_newer_observation_after_cooldown(session):
    _seed(session)
    assert should_emit(session, "price_move", "eia-wti", AS_OF + timedelta(days=7), now=AS_OF + timedelta(days=8))


def test_cooldown_blocks_even_if_new(session):
    _seed(session)
    assert not should_emit(session, "price_move", "eia-wti", AS_OF + timedelta(hours=1), now=AS_OF + timedelta(hours=2))


def test_price_hysteresis():
    assert price_state(96, "normal") == "high"
    assert price_state(92, "high") == "high"  # stays until back inside 90
    assert price_state(92, "normal") == "normal"
    assert price_state(89, "high") == "normal"
    assert price_state(3, "normal") == "low"
    assert price_state(8, "low") == "low"


def test_band_hysteresis():
    assert band_state(90, 100, 200, "inside") == "below"
    assert band_state(102, 100, 200, "below") == "below"  # within 5% exit margin
    assert band_state(110, 100, 200, "below") == "inside"
    assert band_state(198, 100, 200, "above") == "above"


def test_ordinal():
    assert [ordinal(x) for x in (1, 2, 3, 11, 12, 21, 41, 95)] == ["1st", "2nd", "3rd", "11th", "12th", "21st", "41st", "95th"]
