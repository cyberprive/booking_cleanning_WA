"""Application configuration and environment helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass

import pytz


@dataclass(slots=True)
class Settings:
    """Runtime configuration for the booking assistant."""

    calendar_id: str
    google_service_account_file: str
    database_path: str
    timezone: pytz.BaseTzInfo
    slot_minutes: int
    open_hour: int
    close_hour: int
    days_ahead: int
    max_slots: int
    appointment_summary: str
    conversation_ttl_minutes: int

    @classmethod
    def from_env(cls) -> "Settings":
        """Load configuration from environment variables."""
        calendar_id = _require_env("BUSINESS_CALENDAR_ID")
        service_account_file = _require_env("GOOGLE_SERVICE_ACCOUNT_FILE")

        timezone_name = os.getenv("BUSINESS_TIMEZONE", "America/Los_Angeles")
        try:
            timezone = pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unknown timezone: {timezone_name}") from exc

        database_path = os.getenv("DATABASE_PATH", "data/app.db")
        slot_minutes = _get_int("APPOINTMENT_SLOT_MINUTES", 30)
        open_hour = _get_int("BUSINESS_OPEN_HOUR", 9)
        close_hour = _get_int("BUSINESS_CLOSE_HOUR", 17)
        days_ahead = _get_int("SEARCH_DAYS_AHEAD", 14)
        max_slots = _get_int("WHATSAPP_MAX_SLOTS", 5)
        appointment_summary = os.getenv(
            "APPOINTMENT_SUMMARY_TEMPLATE",
            "Appointment with {customer}",
        )
        conversation_ttl = _get_int("CONVERSATION_TTL_MINUTES", 45)

        if close_hour <= open_hour:
            raise ValueError("BUSINESS_CLOSE_HOUR must be after BUSINESS_OPEN_HOUR")

        return cls(
            calendar_id=calendar_id,
            google_service_account_file=service_account_file,
            database_path=database_path,
            timezone=timezone,
            slot_minutes=slot_minutes,
            open_hour=open_hour,
            close_hour=close_hour,
            days_ahead=days_ahead,
            max_slots=max_slots,
            appointment_summary=appointment_summary,
            conversation_ttl_minutes=conversation_ttl,
        )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Environment variable {name} must be an integer") from exc
