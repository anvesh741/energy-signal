from datetime import datetime
from zoneinfo import ZoneInfo

from app.weekly_window import RELEASES, in_weekly_release_window, window_start

ET = ZoneInfo("America/New_York")


def test_retail_window_mon_noon_to_wed_noon():
    assert not in_weekly_release_window(datetime(2024, 10, 28, 10, tzinfo=ET))
    assert in_weekly_release_window(datetime(2024, 10, 28, 12, tzinfo=ET))
    assert in_weekly_release_window(datetime(2024, 10, 29, 9, tzinfo=ET))  # holiday slip to Tuesday
    assert not in_weekly_release_window(datetime(2024, 10, 30, 12, tzinfo=ET))


def test_storage_window_covers_holiday_shifts():
    storage = RELEASES["storage"]
    assert in_weekly_release_window(datetime(2024, 11, 27, 12, tzinfo=ET), storage)  # Thanksgiving-week Wednesday
    assert in_weekly_release_window(datetime(2024, 10, 31, 10, 30, tzinfo=ET), storage)
    assert not in_weekly_release_window(datetime(2024, 11, 2, 9, tzinfo=ET), storage)


def test_window_start_is_the_same_for_every_tick_in_a_window():
    a = window_start(datetime(2024, 10, 28, 13, tzinfo=ET), RELEASES["retail"])
    b = window_start(datetime(2024, 10, 30, 11, tzinfo=ET), RELEASES["retail"])
    assert a == b == datetime(2024, 10, 28, 12, tzinfo=ET)
    assert window_start(datetime(2024, 11, 1, 12, tzinfo=ET), RELEASES["retail"]) is None
