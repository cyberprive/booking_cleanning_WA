import datetime
from typing import Any

import pytz
import pytest
from twilio.request_validator import RequestValidator

from booking_bot import create_app


def _build_app(monkeypatch: pytest.MonkeyPatch, tmp_path, token: str = "secret"):
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("BUSINESS_CALENDAR_ID", "primary")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(tmp_path / "service.json"))
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", token)
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("BUSINESS_TIMEZONE", "UTC")

    monkeypatch.setattr(
        "booking_bot.scheduler.get_calendar_service",
        lambda *args, **kwargs: object(),
    )

    app = create_app()
    app.config.update(TESTING=True)
    return app


def test_webhook_rejects_invalid_signature(monkeypatch: pytest.MonkeyPatch, tmp_path):
    app = _build_app(monkeypatch, tmp_path)

    def _unexpected(*args: Any, **kwargs: Any):  # pragma: no cover - should not run
        raise AssertionError("Availability lookup should not run for invalid signatures")

    monkeypatch.setattr("booking_bot.scheduler.get_available_slots", _unexpected)

    client = app.test_client()
    response = client.post("/webhook", data={"From": "whatsapp:+1234", "Body": "Hi"})

    assert response.status_code == 403


def test_webhook_allows_valid_signature(monkeypatch: pytest.MonkeyPatch, tmp_path):
    token = "secret"
    app = _build_app(monkeypatch, tmp_path, token=token)

    tz = pytz.UTC
    slot_time = tz.localize(datetime.datetime(2023, 5, 1, 12, 0))
    slots_called = {"count": 0}

    def _fake_slots(*args: Any, **kwargs: Any):
        slots_called["count"] += 1
        return [slot_time]

    monkeypatch.setattr("booking_bot.scheduler.get_available_slots", _fake_slots)

    validator = RequestValidator(token)
    params = {"From": "whatsapp:+1234", "Body": "Hi"}
    signature = validator.compute_signature("http://localhost/webhook", params)

    client = app.test_client()
    response = client.post(
        "/webhook",
        data=params,
        headers={"X-Twilio-Signature": signature},
    )

    assert response.status_code == 200
    assert slots_called["count"] == 1
    assert b"Thanks for reaching out" in response.data
