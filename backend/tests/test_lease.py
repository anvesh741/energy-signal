from datetime import datetime, timedelta, timezone

import app.scheduler as sched

NOW = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)


def test_second_process_cannot_take_a_live_lease(engine, monkeypatch):
    monkeypatch.setattr(sched, "engine", engine)
    assert sched.acquire_lease("a", now=NOW)
    assert not sched.acquire_lease("b", now=NOW + timedelta(minutes=1))
    assert sched.acquire_lease("a", now=NOW + timedelta(minutes=2))  # renew


def test_expired_lease_is_taken_over(engine, monkeypatch):
    monkeypatch.setattr(sched, "engine", engine)
    assert sched.acquire_lease("a", now=NOW)
    assert sched.acquire_lease("b", now=NOW + timedelta(minutes=6))
    assert not sched.acquire_lease("a", now=NOW + timedelta(minutes=7))
