from datetime import timedelta

from booking_bot import storage


def test_save_and_get_conversation(tmp_path):
    db_path = tmp_path / "test.db"
    store = storage.ConversationStore(str(db_path))

    store.save("whatsapp:+15551234567", storage.ConversationState.AWAITING_SLOT, ["2023-05-01T17:00:00+00:00"])
    conversation = store.get("whatsapp:+15551234567")

    assert conversation is not None
    assert conversation.phone_number == "whatsapp:+15551234567"
    assert conversation.state == storage.ConversationState.AWAITING_SLOT
    assert conversation.slots == ["2023-05-01T17:00:00+00:00"]


def test_conversation_expiration(tmp_path):
    db_path = tmp_path / "test.db"
    store = storage.ConversationStore(str(db_path))

    store.save("whatsapp:+15551234567", storage.ConversationState.AWAITING_SLOT, ["2023-05-01T17:00:00+00:00"])
    conversation = store.get("whatsapp:+15551234567")
    assert conversation is not None

    past_time = conversation.created_at + timedelta(minutes=90)
    assert conversation.is_expired(60, past_time)


def test_clear_conversation(tmp_path):
    db_path = tmp_path / "test.db"
    store = storage.ConversationStore(str(db_path))

    store.save("whatsapp:+15551234567", storage.ConversationState.AWAITING_SLOT, ["2023-05-01T17:00:00+00:00"])
    store.clear("whatsapp:+15551234567")

    assert store.get("whatsapp:+15551234567") is None
