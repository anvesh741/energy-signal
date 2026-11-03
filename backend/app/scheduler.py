"""Dedicated scheduler process. Run:  python -m app.scheduler  (or --once).

Only the holder of the single-row SchedulerLease runs jobs, so a second process
(or a --reload child) stands by instead of double-running. The lease is taken with
one conditional UPDATE, which SQLite executes atomically.
"""

import argparse
import logging
import os
import socket
import threading
import uuid
from datetime import datetime, timedelta

import httpx
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.config import settings
from app.db import engine, init_db, session_scope
from app.jobs import (
    post_refresh_derived,
    refresh_eia_hourly,
    refresh_eia_prices,
    refresh_eia_weekly,
    refresh_ember,
    refresh_pink_sheet,
    run_all,
)
from app.models import SchedulerLease
from app.timeutil import utc_now
from app.weekly_window import RELEASES

log = logging.getLogger("scheduler")
OWNER = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
TTL = timedelta(minutes=5)


def acquire_lease(owner: str = OWNER, now: datetime | None = None, ttl: timedelta = TTL) -> bool:
    """Take or renew the lease. True if `owner` holds it afterwards."""
    now = now or utc_now()
    stmt = (
        update(SchedulerLease)
        .where(
            SchedulerLease.id == 1,
            or_(SchedulerLease.owner == owner, SchedulerLease.expires_at < now),
        )
        .values(owner=owner, expires_at=now + ttl)
    )
    with Session(engine) as session:
        if session.exec(stmt).rowcount:
            session.commit()
            return True
        if session.get(SchedulerLease, 1) is not None:
            return False  # someone else holds a live lease
        try:
            session.add(SchedulerLease(id=1, owner=owner, expires_at=now + ttl))
            session.commit()
            return True
        except IntegrityError:
            return False  # lost the insert race


def release_lease(owner: str = OWNER) -> None:
    with Session(engine) as session:
        session.exec(
            update(SchedulerLease).where(SchedulerLease.owner == owner).values(expires_at=utc_now())
        )
        session.commit()


def start_heartbeat(interval_s: int = 60) -> None:
    """Renew (or, on standby, take over an expired) lease on a thread of its own, so a
    long backfill never lets the lease lapse mid-job."""

    def loop():
        while not stop.wait(interval_s):
            try:
                acquire_lease()
            except Exception:  # noqa: BLE001
                log.exception("lease heartbeat failed")

    threading.Thread(target=loop, name="lease-heartbeat", daemon=True).start()


stop = threading.Event()


def guarded(fn):
    def wrapper():
        if not acquire_lease():
            log.info("standby: lease held by another process; skipping %s", fn.__name__)
            return
        try:
            with session_scope() as session, httpx.Client() as client:
                post_refresh_derived(session, fn(session, client) or set())
        except Exception:  # noqa: BLE001 - one bad job must not kill the scheduler
            log.exception("job %s failed", fn.__name__)

    wrapper.__name__ = fn.__name__
    return wrapper


@guarded
def job_hourly(session, client):
    return refresh_eia_hourly(session, client) if settings.eia_api_key else set()


@guarded
def job_prices(session, client):
    return refresh_eia_prices(session, client) if settings.eia_api_key else set()


@guarded
def job_weekly(session, client):
    if not settings.eia_api_key:
        return set()
    changed = set()
    for release in RELEASES:
        changed |= refresh_eia_weekly(session, client, release)
    return changed


@guarded
def job_global(session, client):
    changed = refresh_ember(session, client) if settings.ember_api_key else set()
    return changed | refresh_pink_sheet(session, client)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="refresh everything once (forcing weekly) and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # request URLs carry api_key
    init_db()

    start_heartbeat()
    if args.once:
        if not acquire_lease():
            raise SystemExit("another scheduler holds the lease; not running")
        try:
            with session_scope() as session:
                changed = run_all(session, weekly_force=True)
            log.info("refreshed; new observations for: %s", ", ".join(sorted(changed)) or "nothing")
        finally:
            stop.set()
            release_lease()
        return

    if not settings.scheduler_enabled:
        raise SystemExit("SCHEDULER_ENABLED=false")
    if acquire_lease():
        with session_scope() as session:
            run_all(session, weekly_force=True)
    else:
        log.info("standby: another scheduler holds the lease (%s)", OWNER)

    scheduler = BlockingScheduler(
        timezone="UTC",
        executors={"default": ThreadPoolExecutor(1)},  # one writer at a time
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 600},
    )
    scheduler.add_job(job_hourly, "interval", minutes=45, id="eia-hourly")
    scheduler.add_job(job_prices, "interval", hours=6, id="eia-prices")
    scheduler.add_job(job_weekly, "interval", minutes=60, id="eia-weekly-window")
    scheduler.add_job(job_global, "interval", hours=24, id="ember-pink-sheet")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        stop.set()
        release_lease()


if __name__ == "__main__":
    main()
