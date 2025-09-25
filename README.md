# WhatsApp Booking Assistant

This project provides a lightweight Flask application that responds to WhatsApp
messages, offers available appointment times, and books the selected slot into a
Google Calendar. It is designed to be deployed behind the Twilio WhatsApp
sandbox or a WhatsApp Business account webhook.

## Features

- Automatically replies to inbound WhatsApp messages with the next available
  appointment slots pulled from Google Calendar.
- Tracks the state of each conversation so the customer can reply with the slot
  number they prefer.
- Creates the confirmed appointment directly in the configured Google Calendar
  and sends a WhatsApp confirmation message back to the customer.

## Prerequisites

1. **Twilio WhatsApp** – Configure a WhatsApp sender in Twilio and set the
   inbound webhook to point to this application's `/webhook` endpoint.
2. **Google Cloud project** – Create a service account with access to the target
   Google Calendar and download its JSON credentials file.
3. **Python 3.11+** – The app and tests require Python 3.11 or newer.

## Setup

1. Clone the repository and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install pytest  # for running the test suite
   ```

2. Copy `.env.example` to `.env` and fill in the required values. The critical
   variables are:

   - `BUSINESS_CALENDAR_ID`: ID of the Google Calendar that holds
     appointments.
   - `GOOGLE_SERVICE_ACCOUNT_FILE`: Path to the service account JSON
     credentials file.

   Optional variables let you tune business hours, slot length, and the message
   template used in confirmations.

3. Ensure the service account has "Make changes to events" access to the
   configured calendar. Share the calendar with the service account's email
   address via Google Calendar settings.

## Running the application

Export the environment variables (Flask will load `.env` automatically) and
start the development server:

```bash
export FLASK_APP=booking_bot:create_app
flask run --host=0.0.0.0 --port=8000
```

Expose the server to Twilio (e.g., via `ngrok`) and configure the Twilio
WhatsApp webhook URL to `https://<your-domain>/webhook`.

### Conversation flow

1. Customer sends any message to the business on WhatsApp.
2. The webhook responds with the next available appointment slots pulled from
   Google Calendar.
3. Customer replies with the number of their preferred slot.
4. The app books the appointment in Google Calendar and sends a confirmation
   message back to the customer.

If no slots are available or the customer replies with an invalid option, the
app provides guidance to try again later.

## Testing

Run the unit tests with:

```bash
pytest
```

The tests cover the slot scheduling logic and the SQLite conversation store.
