"""Utilities for interacting with Google Calendar."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Iterable, List, Sequence

import pytz
from dateutil import parser as date_parser
from googleapiclient.discovery import build
from google.oauth2 import service_account


DEFAULT_SCOPES = ["https://www.googleapis.com/auth/calendar"]


@dataclass(slots=True)
class BusyInterval:
    """Represents a busy period on the calendar."""

    start: datetime
    end: datetime


def get_calendar_service(credentials_file: str, scopes: Sequence[str] | None = None):
    """Build a Google Calendar service client."""
    credentials = service_account.Credentials.from_service_account_file(
        credentials_file,
        scopes=scopes or DEFAULT_SCOPES,
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO formatted datetime string into an aware datetime."""
    dt = date_parser.isoparse(value)
    if dt.tzinfo is None:  # pragma: no cover - defensive guard
        raise ValueError("Datetime must be timezone aware")
    return dt


def fetch_busy_intervals(
    service,
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
) -> List[BusyInterval]:
    """Fetch busy intervals from Google Calendar between the provided times."""
    request_body = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "timeZone": getattr(time_min.tzinfo, "zone", None) if time_min.tzinfo else None,
        "items": [{"id": calendar_id}],
    }
    response = service.freebusy().query(body=request_body).execute()
    busy_windows = response["calendars"].get(calendar_id, {}).get("busy", [])
    return [
        BusyInterval(parse_iso_datetime(interval["start"]), parse_iso_datetime(interval["end"]))
        for interval in busy_windows
    ]


def compute_available_slots(
    busy_intervals: Iterable[BusyInterval],
    start_time: datetime,
    timezone: pytz.BaseTzInfo,
    days_ahead: int,
    slot_duration: timedelta,
    max_slots: int,
    open_hour: int,
    close_hour: int,
) -> List[datetime]:
    """Compute candidate appointment slots given busy intervals."""
    busy = [
        BusyInterval(interval.start.astimezone(timezone), interval.end.astimezone(timezone))
        for interval in busy_intervals
    ]
    busy.sort(key=lambda interval: interval.start)

    results: List[datetime] = []
    current_day = start_time.astimezone(timezone).date()

    for day_offset in range(days_ahead + 1):
        day = current_day + timedelta(days=day_offset)
        day_start = timezone.localize(datetime.combine(day, time(hour=open_hour)))
        day_end = timezone.localize(datetime.combine(day, time(hour=close_hour)))

        candidate = max(day_start, start_time.astimezone(timezone)) if day_offset == 0 else day_start
        candidate = _align_to_slot(candidate, slot_duration, day_start)
        while candidate + slot_duration <= day_end:
            if not _is_overlapping(candidate, candidate + slot_duration, busy):
                results.append(candidate)
                if len(results) >= max_slots:
                    return results
            candidate += slot_duration

    return results


def get_available_slots(
    service,
    calendar_id: str,
    timezone: pytz.BaseTzInfo,
    *,
    days_ahead: int,
    slot_minutes: int,
    max_slots: int,
    open_hour: int,
    close_hour: int,
) -> List[datetime]:
    """Return a list of available appointment start times."""
    start_time = datetime.now(timezone)
    slot_duration = timedelta(minutes=slot_minutes)
    search_end = timezone.localize(
        datetime.combine((start_time + timedelta(days=days_ahead)).date(), time(hour=close_hour))
    )

    busy_intervals = fetch_busy_intervals(service, calendar_id, start_time, search_end)
    return compute_available_slots(
        busy_intervals,
        start_time,
        timezone,
        days_ahead,
        slot_duration,
        max_slots,
        open_hour,
        close_hour,
    )


def book_slot(
    service,
    calendar_id: str,
    slot_start_iso: str,
    *,
    duration_minutes: int,
    timezone: str,
    summary: str,
    description: str | None = None,
):
    """Create an event in Google Calendar for the selected slot."""
    slot_start = parse_iso_datetime(slot_start_iso)
    slot_end = slot_start + timedelta(minutes=duration_minutes)

    event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": slot_start.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": slot_end.isoformat(),
            "timeZone": timezone,
        },
    }

    return service.events().insert(calendarId=calendar_id, body=event).execute()


def _is_overlapping(start: datetime, end: datetime, busy: Sequence[BusyInterval]) -> bool:
    """Return True if the candidate window overlaps any busy interval."""
    for interval in busy:
        if start < interval.end and end > interval.start:
            return True
    return False


def _align_to_slot(candidate: datetime, slot_duration: timedelta, reference: datetime) -> datetime:
    """Round the candidate time up to the nearest slot boundary."""
    candidate = candidate.replace(second=0, microsecond=0)
    delta = candidate - reference
    if delta < timedelta(0):  # pragma: no cover - defensive guard
        return reference
    remainder = delta % slot_duration
    if remainder:
        candidate += slot_duration - remainder
    return candidate
