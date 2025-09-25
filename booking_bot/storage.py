"""Persistence utilities for tracking WhatsApp conversations."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional


ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


class ConversationState(str, Enum):
    """States a conversation can be in."""

    AWAITING_SLOT = "awaiting_slot"


@dataclass(slots=True)
class Conversation:
    """Stored metadata about a WhatsApp conversation."""

    phone_number: str
    state: ConversationState
    slots: list[str]
    created_at: datetime

    def is_expired(self, ttl_minutes: int, current_time: datetime) -> bool:
        """Check whether the conversation has expired based on TTL."""
        delta = current_time - self.created_at
        return delta > timedelta(minutes=ttl_minutes)


class ConversationStore:
    """SQLite-backed conversation persistence."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    phone TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    slots TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, phone: str, state: ConversationState, slots: Iterable[str]) -> None:
        """Persist or update a conversation."""
        payload = json.dumps(list(slots))
        created_at = datetime.now(timezone.utc).strftime(ISO_FORMAT)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (phone, state, slots, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET state=excluded.state, slots=excluded.slots, created_at=excluded.created_at
                """,
                (phone, state.value, payload, created_at),
            )
            conn.commit()

    def get(self, phone: str) -> Optional[Conversation]:
        """Retrieve a conversation by phone number."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT phone, state, slots, created_at FROM conversations WHERE phone = ?",
                (phone,),
            ).fetchone()
        if not row:
            return None

        slots = json.loads(row[2])
        created_at = datetime.strptime(row[3], ISO_FORMAT)
        return Conversation(
            phone_number=row[0],
            state=ConversationState(row[1]),
            slots=slots,
            created_at=created_at,
        )

    def clear(self, phone: str) -> None:
        """Delete a conversation once it is completed."""
        with self._connect() as conn:
            conn.execute("DELETE FROM conversations WHERE phone = ?", (phone,))
            conn.commit()


def ensure_directory_exists(database_path: str) -> None:
    """Ensure the directory for the SQLite database exists."""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
