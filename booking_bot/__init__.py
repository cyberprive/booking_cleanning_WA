"""Flask application factory for the WhatsApp booking assistant."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

from . import scheduler, storage
from .config import Settings

logger = logging.getLogger(__name__)


def _parse_slot_selection(message: str, slot_count: int) -> int | None:
    """Extract a numeric slot selection from a WhatsApp message."""
    match = re.search(r"(\d+)", message)
    if not match:
        return None
    index = int(match.group(1)) - 1
    if 0 <= index < slot_count:
        return index
    return None


def create_app() -> Flask:
    """Create and configure the Flask application."""
    load_dotenv()

    settings = Settings.from_env()
    app = Flask(__name__)

    storage.ensure_directory_exists(settings.database_path)
    conversation_store = storage.ConversationStore(settings.database_path)
    calendar_service = scheduler.get_calendar_service(settings.google_service_account_file)

    def _as_twiml(resp: MessagingResponse):
        return str(resp), 200, {"Content-Type": "application/xml"}

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        """Health probe endpoint."""
        return {"status": "ok"}, 200

    @app.post("/webhook")
    def whatsapp_webhook():
        """Handle inbound WhatsApp messages from Twilio."""
        from_number = request.form.get("From", "")
        message_body = request.form.get("Body", "").strip()
        logger.info("Received message from %s: %s", from_number, message_body)

        response = MessagingResponse()
        now = datetime.now(settings.timezone)

        existing = conversation_store.get(from_number)
        if existing and existing.is_expired(settings.conversation_ttl_minutes, now):
            conversation_store.clear(from_number)
            existing = None

        if not existing or existing.state != storage.ConversationState.AWAITING_SLOT:
            available_slots = scheduler.get_available_slots(
                calendar_service,
                settings.calendar_id,
                settings.timezone,
                days_ahead=settings.days_ahead,
                slot_minutes=settings.slot_minutes,
                max_slots=settings.max_slots,
                open_hour=settings.open_hour,
                close_hour=settings.close_hour,
            )

            if not available_slots:
                response.message(
                    "We couldn't find any open appointment slots right now. "
                    "Please try again later or contact the business directly."
                )
                return _as_twiml(response)

            conversation_store.save(
                from_number,
                storage.ConversationState.AWAITING_SLOT,
                [slot.isoformat() for slot in available_slots],
            )

            formatted_slots = [
                f"{idx + 1}. {slot.strftime('%A %b %d at %I:%M %p')}"
                for idx, slot in enumerate(available_slots)
            ]
            response.message(
                "Thanks for reaching out! Here are our next available appointments:\n"
                + "\n".join(formatted_slots)
                + "\nReply with the number of your preferred time to confirm your booking."
            )
            return _as_twiml(response)

        slot_index = _parse_slot_selection(message_body, len(existing.slots))
        if slot_index is None:
            response.message(
                "Please reply with the number of the appointment time you'd like to book."
            )
            return _as_twiml(response)

        try:
            slot_start = existing.slots[slot_index]
            booking = scheduler.book_slot(
                calendar_service,
                settings.calendar_id,
                slot_start,
                duration_minutes=settings.slot_minutes,
                timezone=settings.timezone.zone,
                summary=settings.appointment_summary.format(customer=from_number),
                description=f"WhatsApp booking from {from_number}",
            )
        except Exception:  # pragma: no cover - Google API errors are logged
            logger.exception("Failed to book appointment for %s", from_number)
            response.message(
                "Something went wrong while scheduling your appointment. "
                "Please try again or contact the business directly."
            )
            return _as_twiml(response)

        conversation_store.clear(from_number)

        start_time = scheduler.parse_iso_datetime(slot_start).astimezone(settings.timezone)
        end_time = start_time + timedelta(minutes=settings.slot_minutes)
        confirmation = (
            f"You're booked! We'll see you on {start_time.strftime('%A %b %d')} "
            f"from {start_time.strftime('%I:%M %p')} to {end_time.strftime('%I:%M %p')}."
        )
        if booking.get("hangoutLink"):
            confirmation += f" Join link: {booking['hangoutLink']}"

        response.message(confirmation)
        return _as_twiml(response)

    return app


__all__ = ["create_app"]
