from app.services.bitable_views import InMemoryBitableViewDataSource, get_view_records
from app.services.permissions import Actor


def test_inbox_view_projects_stage03_fields_and_applies_customer_scope() -> None:
    data_source = InMemoryBitableViewDataSource()
    _add_message(
        data_source,
        record_id="message-1",
        customer_id="customer-1",
        telegram_chat_id="chat-1",
        telegram_user_id="user-1",
        received_at="2026-07-06T10:00:00+00:00",
    )
    _add_message(
        data_source,
        record_id="message-2",
        customer_id="customer-2",
        telegram_chat_id="chat-2",
        telegram_user_id="user-2",
        received_at="2026-07-06T10:01:00+00:00",
    )
    _add_message(
        data_source,
        record_id="message-unbound",
        customer_id=None,
        telegram_chat_id="chat-unbound",
        telegram_user_id="user-unbound",
        binding_status="needs_manual_binding",
        received_at="2026-07-06T10:02:00+00:00",
    )
    actor = Actor(
        actor_type="user",
        actor_id="sales-1",
        role="sales",
        customer_ids=frozenset({"customer-1"}),
    )

    response = get_view_records("telegram_inbox", data_source=data_source, actor=actor)

    assert [record.id for record in response.records] == ["message-1"]
    assert response.records[0].fields == {
        "message_id": "message-1",
        "telegram_update_id": "update-message-1",
        "telegram_chat_id": "chat-1",
        "telegram_user_id": "user-1",
        "customer_id": "customer-1",
        "binding_status": "bound",
        "message_type": "text",
        "text_preview": "preview for message-1",
        "processing_status": "queued",
        "outbox_status": "pending",
        "last_error_code": None,
        "received_at": "2026-07-06T10:00:00+00:00",
        "processed_at": None,
    }


def test_inbox_view_has_stable_order_and_limit() -> None:
    data_source = InMemoryBitableViewDataSource()
    for index in range(205):
        _add_message(
            data_source,
            record_id=f"message-{index:03d}",
            customer_id=f"customer-{index:03d}",
            telegram_chat_id=f"chat-{index:03d}",
            telegram_user_id=f"user-{index:03d}",
            received_at=f"2026-07-06T10:{index // 60:02d}:{index % 60:02d}+00:00",
        )

    default_response = get_view_records("telegram_inbox", data_source=data_source)
    custom_response = get_view_records(
        "telegram_inbox",
        data_source=data_source,
        limit=250,
    )
    small_response = get_view_records(
        "telegram_inbox",
        data_source=data_source,
        limit=2,
    )

    assert len(default_response.records) == 100
    assert len(custom_response.records) == 200
    assert [record.id for record in small_response.records] == [
        "message-204",
        "message-203",
    ]


def test_inbox_view_redacts_secret_and_raw_payload() -> None:
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "messages",
        record_id="message-secret",
        fields={
            "telegram_update_id": "update-secret",
            "telegram_chat_id": "chat-secret",
            "telegram_user_id": "user-secret",
            "customer_id": "customer-secret",
            "binding_status": "bound",
            "message_type": "text",
            "normalized_text": "safe preview",
            "processing_status": "queued",
            "outbox_status": "pending",
            "last_error_code": None,
            "received_at": "2026-07-06T10:00:00+00:00",
            "processed_at": None,
            "raw_text": "full raw customer message",
            "raw_update": {"secret_like": "do-not-return"},
            "webhook_secret": "stage-secret",
            "bot_token": "123456789:token-value",
        },
    )

    response = get_view_records("telegram_inbox", data_source=data_source)
    fields = response.records[0].fields

    assert fields["message_id"] == "message-secret"
    assert fields["text_preview"] == "safe preview"
    assert "raw_text" not in fields
    assert "raw_update" not in fields
    assert "webhook_secret" not in fields
    assert "bot_token" not in fields
    assert "stage-secret" not in str(response.model_dump())
    assert "123456789:token-value" not in str(response.model_dump())


def _add_message(
    data_source: InMemoryBitableViewDataSource,
    *,
    record_id: str,
    customer_id: str | None,
    telegram_chat_id: str,
    telegram_user_id: str,
    binding_status: str = "bound",
    received_at: str,
) -> None:
    data_source.add_record(
        "messages",
        record_id=record_id,
        fields={
            "telegram_update_id": f"update-{record_id}",
            "telegram_chat_id": telegram_chat_id,
            "telegram_user_id": telegram_user_id,
            "customer_id": customer_id,
            "binding_status": binding_status,
            "message_type": "text",
            "normalized_text": f"preview for {record_id}",
            "processing_status": "queued",
            "outbox_status": "pending",
            "last_error_code": None,
            "received_at": received_at,
            "processed_at": None,
        },
    )
