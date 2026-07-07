from fastapi.testclient import TestClient

from app.api.deps import get_system_actor
from app.api.routes.views import get_bitable_view_data_source
from app.main import create_app
from app.services.bitable_views import InMemoryBitableViewDataSource
from app.services.permissions import Actor


def test_stage04_views_project_binding_send_request_and_intent_queue() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "telegram_customer_bindings",
        record_id="binding-1",
        fields={
            "customer_id": "customer-1",
            "binding_scope": "chat_user",
            "telegram_chat_id": "chat-1",
            "telegram_user_id": "user-1",
            "status": "active",
            "label": "Stage04 test",
            "created_by": "manager-1",
            "created_at": "2026-07-06T00:00:00+00:00",
            "updated_at": "2026-07-06T00:01:00+00:00",
            "ignored_field": "not projected",
        },
    )
    data_source.add_record(
        "telegram_send_requests",
        record_id="send-1",
        fields={
            "target_chat_id": "test-chat",
            "status": "sent",
            "requested_by_actor_id": "manager-1",
            "confirmed_by_actor_id": "manager-2",
            "telegram_response_summary": {
                "ok": True,
                "telegram_message_id": 42,
            },
            "last_error_code": None,
            "sent_at": "2026-07-06T00:00:10+00:00",
            "trace_id": "tg-send:send-1",
        },
    )
    data_source.add_record(
        "messages",
        record_id="message-1",
        fields={
            "customer_id": "customer-1",
            "binding_status": "bound",
            "intent_status": "intent_ready",
            "intent_type": None,
            "processing_status": "processed",
            "received_at": "2026-07-06T00:00:00+00:00",
            "trace_id": "tg:update-1",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="manager-1",
        role="manager",
    )

    with TestClient(app) as client:
        bindings_response = client.get("/views/telegram_bindings/records")
        send_response = client.get("/views/telegram_send_requests/records")
        intent_response = client.get("/views/telegram_intent_queue/records")

    assert bindings_response.status_code == 200
    assert bindings_response.json()["records"][0]["fields"] == {
        "binding_id": "binding-1",
        "customer_id": "customer-1",
        "binding_scope": "chat_user",
        "telegram_chat_id": "chat-1",
        "telegram_user_id": "user-1",
        "status": "active",
        "label": "Stage04 test",
        "created_by": "manager-1",
        "created_at": "2026-07-06T00:00:00+00:00",
        "updated_at": "2026-07-06T00:01:00+00:00",
    }
    assert send_response.status_code == 200
    assert send_response.json()["records"][0]["fields"] == {
        "request_id": "send-1",
        "target_chat_id": "test-chat",
        "status": "sent",
        "requested_by_actor_id": "manager-1",
        "confirmed_by_actor_id": "manager-2",
        "telegram_response_summary": {
            "ok": True,
            "telegram_message_id": 42,
        },
        "last_error_code": None,
        "sent_at": "2026-07-06T00:00:10+00:00",
        "trace_id": "tg-send:send-1",
    }
    assert intent_response.status_code == 200
    assert intent_response.json()["records"][0]["fields"] == {
        "message_id": "message-1",
        "customer_id": "customer-1",
        "binding_status": "bound",
        "intent_status": "intent_ready",
        "intent_type": None,
        "processing_status": "processed",
        "received_at": "2026-07-06T00:00:00+00:00",
        "trace_id": "tg:update-1",
    }


def test_stage04_views_mask_telegram_identifiers_for_sales_actor() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "telegram_customer_bindings",
        record_id="binding-1",
        fields={
            "customer_id": "customer-1",
            "binding_scope": "chat",
            "telegram_chat_id": "chat-secret",
            "telegram_user_id": None,
            "status": "active",
        },
    )
    data_source.add_record(
        "telegram_send_requests",
        record_id="send-1",
        fields={
            "target_chat_id": "test-chat",
            "status": "sent",
            "telegram_response_summary": {"ok": True},
            "trace_id": "tg-send:send-1",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="sales-1",
        role="sales",
        customer_ids=frozenset({"customer-1"}),
    )

    with TestClient(app) as client:
        bindings_response = client.get("/views/telegram_bindings/records")
        send_response = client.get("/views/telegram_send_requests/records")

    assert bindings_response.status_code == 200
    assert bindings_response.json()["records"][0]["fields"]["telegram_chat_id"] == (
        "[masked]"
    )
    assert bindings_response.json()["records"][0]["fields"]["telegram_user_id"] == (
        "[masked]"
    )
    assert send_response.status_code == 200
    assert send_response.json()["records"] == []


def test_stage04_views_hide_unbound_conflict_and_send_rows_from_sales_actor() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "messages",
        record_id="message-bound",
        fields={
            "telegram_update_id": "update-bound",
            "telegram_chat_id": "chat-bound",
            "telegram_message_id": "message-telegram-bound",
            "telegram_user_id": "user-bound",
            "customer_id": "customer-1",
            "binding_status": "bound",
            "message_type": "text",
            "normalized_text": "bound preview",
            "processing_status": "processed",
            "outbox_status": "processed",
            "intent_status": "intent_ready",
            "intent_type": None,
            "received_at": "2026-07-06T00:00:00+00:00",
            "trace_id": "tg:bound",
        },
    )
    data_source.add_record(
        "messages",
        record_id="message-unbound",
        fields={
            "telegram_update_id": "update-unbound",
            "telegram_chat_id": "chat-unbound",
            "telegram_message_id": "message-telegram-unbound",
            "telegram_user_id": "user-unbound",
            "customer_id": None,
            "binding_status": "needs_manual_binding",
            "message_type": "text",
            "normalized_text": "unbound preview",
            "processing_status": "processed",
            "outbox_status": "processed",
            "intent_status": "needs_review",
            "intent_type": None,
            "received_at": "2026-07-06T00:01:00+00:00",
            "trace_id": "tg:unbound",
        },
    )
    data_source.add_record(
        "messages",
        record_id="message-conflict",
        fields={
            "telegram_update_id": "update-conflict",
            "telegram_chat_id": "chat-conflict",
            "telegram_message_id": "message-telegram-conflict",
            "telegram_user_id": "user-conflict",
            "customer_id": None,
            "binding_status": "binding_conflict",
            "message_type": "text",
            "normalized_text": "conflict preview",
            "processing_status": "processed",
            "outbox_status": "processed",
            "intent_status": "needs_review",
            "intent_type": None,
            "received_at": "2026-07-06T00:02:00+00:00",
            "trace_id": "tg:conflict",
        },
    )
    data_source.add_record(
        "telegram_send_requests",
        record_id="send-1",
        fields={
            "target_chat_id": "test-chat",
            "status": "sent",
            "telegram_response_summary": {"ok": True},
            "trace_id": "tg-send:send-1",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="sales-1",
        role="sales",
        customer_ids=frozenset({"customer-1"}),
    )

    with TestClient(app) as client:
        inbox_response = client.get("/views/telegram_inbox/records")
        send_response = client.get("/views/telegram_send_requests/records")

    assert inbox_response.status_code == 200
    assert [record["id"] for record in inbox_response.json()["records"]] == [
        "message-bound"
    ]
    assert send_response.status_code == 200
    assert send_response.json()["records"] == []
