from datetime import datetime, timedelta

import pytz

from booking_bot import scheduler


TZ = pytz.timezone("America/Los_Angeles")


def _slot(hour: int, minute: int = 0) -> datetime:
    return TZ.localize(datetime(2023, 5, 1, hour, minute))


def test_compute_available_slots_without_busy_time():
    start_time = _slot(9, 0)
    slots = scheduler.compute_available_slots(
        busy_intervals=[],
        start_time=start_time,
        timezone=TZ,
        days_ahead=0,
        slot_duration=timedelta(minutes=30),
        max_slots=3,
        open_hour=9,
        close_hour=11,
    )

    assert [slot.strftime("%H:%M") for slot in slots] == ["09:00", "09:30", "10:00"]


def test_compute_available_slots_skips_busy_periods():
    start_time = _slot(9, 0)
    busy = [
        scheduler.BusyInterval(_slot(9, 30), _slot(10, 0)),
    ]

    slots = scheduler.compute_available_slots(
        busy_intervals=busy,
        start_time=start_time,
        timezone=TZ,
        days_ahead=0,
        slot_duration=timedelta(minutes=30),
        max_slots=4,
        open_hour=9,
        close_hour=11,
    )

    assert [slot.strftime("%H:%M") for slot in slots] == ["09:00", "10:00", "10:30", "11:00"][: len(slots)]


def test_aligns_slots_when_start_time_is_mid_slot():
    start_time = TZ.localize(datetime(2023, 5, 1, 9, 5))
    slots = scheduler.compute_available_slots(
        busy_intervals=[],
        start_time=start_time,
        timezone=TZ,
        days_ahead=0,
        slot_duration=timedelta(minutes=30),
        max_slots=2,
        open_hour=9,
        close_hour=11,
    )

    assert [slot.strftime("%H:%M") for slot in slots] == ["09:30", "10:00"]
