from fastapi.testclient import TestClient

from app.api.deps import get_system_actor
from app.api.routes.views import get_bitable_view_data_source
from app.main import create_app
from app.services.bitable_views import InMemoryBitableViewDataSource
from app.services.permissions import Actor


def test_stage05_service_drafts_and_pending_confirmation_views() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "service_drafts",
        record_id="draft-confirmable",
        fields={
            "draft_type": "customer_reply",
            "status": "pending_confirmation",
            "customer_id": "customer-1",
            "source_message_id": "message-1",
            "created_by_type": "agent",
            "created_by_id": "customer_reply_draft_agent",
            "confidence": "0.9300",
            "missing_fields": [],
            "risk_flags": ["requires_test_send"],
            "payload": {"reply_text": "raw reply text must not be projected"},
            "payload_summary": {"reply_text": "We are checking the account."},
            "trace_id": "tg:message-1",
            "created_at": "2026-07-07T01:00:00+00:00",
        },
    )
    data_source.add_record(
        "service_drafts",
        record_id="draft-missing-fields",
        fields={
            "draft_type": "recharge",
            "status": "pending_confirmation",
            "customer_id": "customer-1",
            "source_message_id": "message-1",
            "created_by_type": "agent",
            "created_by_id": "recharge_draft_agent",
            "confidence": "0.6500",
            "missing_fields": ["amount"],
            "risk_flags": [],
            "payload_summary": {"account_hint": "act_1001"},
            "trace_id": "tg:message-1",
            "created_at": "2026-07-07T01:01:00+00:00",
        },
    )
    data_source.add_record(
        "service_drafts",
        record_id="draft-confirmed",
        fields={
            "draft_type": "recharge",
            "status": "confirmed",
            "customer_id": "customer-1",
            "source_message_id": "message-1",
            "created_by_type": "agent",
            "created_by_id": "recharge_draft_agent",
            "confidence": "0.9200",
            "missing_fields": [],
            "risk_flags": [],
            "payload_summary": {"amount": "100", "currency": "USD"},
            "trace_id": "tg:message-1",
            "created_at": "2026-07-07T01:02:00+00:00",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source

    with TestClient(app) as client:
        drafts_response = client.get("/views/service_drafts/records")
        pending_response = client.get("/views/pending_confirmation/records")

    assert drafts_response.status_code == 200
    assert drafts_response.json()["records"][0]["fields"] == {
        "draft_id": "draft-confirmable",
        "draft_type": "customer_reply",
        "status": "pending_confirmation",
        "customer_id": "customer-1",
        "source_message_id": "message-1",
        "created_by_type": "agent",
        "created_by_id": "customer_reply_draft_agent",
        "confidence": "0.9300",
        "missing_fields": [],
        "risk_flags": ["requires_test_send"],
        "payload_summary": {"reply_text": "We are checking the account."},
        "trace_id": "tg:message-1",
        "created_at": "2026-07-07T01:00:00+00:00",
    }
    assert "payload" not in drafts_response.json()["records"][0]["fields"]

    assert pending_response.status_code == 200
    assert pending_response.json()["records"] == [
        {
            "id": "draft-confirmable",
            "fields": {
                "draft_id": "draft-confirmable",
                "draft_type": "customer_reply",
                "customer_id": "customer-1",
                "source_message_id": "message-1",
                "confidence": "0.9300",
                "risk_flags": ["requires_test_send"],
                "confirm_action": "create_customer_reply_send_request",
                "trace_id": "tg:message-1",
                "created_at": "2026-07-07T01:00:00+00:00",
            },
        }
    ]


def test_agent_review_queue_combines_manual_review_and_failed_runs() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "messages",
        record_id="message-review",
        fields={
            "customer_id": "customer-1",
            "intent_status": "manual_review",
            "intent_type": None,
            "last_error_code": "low_confidence",
            "trace_id": "tg:review",
            "received_at": "2026-07-07T02:00:00+00:00",
        },
    )
    data_source.add_record(
        "messages",
        record_id="message-failed",
        fields={
            "customer_id": "customer-2",
            "intent_status": "agent_failed",
            "intent_type": "recharge",
            "last_error_code": "router_runtime_error",
            "trace_id": "tg:failed-message",
            "received_at": "2026-07-07T02:01:00+00:00",
        },
    )
    data_source.add_record(
        "service_drafts",
        record_id="draft-review",
        fields={
            "draft_type": "card_binding",
            "status": "manual_review",
            "customer_id": "customer-1",
            "source_message_id": "message-review",
            "review_reason": "sensitive payment data detected",
            "risk_flags": ["sensitive_payment_data_detected"],
            "trace_id": "tg:review",
            "created_at": "2026-07-07T02:02:00+00:00",
        },
    )
    data_source.add_record(
        "agent_runs",
        record_id="run-failed",
        fields={
            "message_id": "message-failed",
            "status": "failed",
            "error_code": "openrouter_timeout",
            "error_message_redacted": "OpenRouter request timed out",
            "trace_id": "tg:failed-run",
            "started_at": "2026-07-07T02:03:00+00:00",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="manager-1",
        role="manager",
    )

    with TestClient(app) as client:
        response = client.get("/views/agent_review_queue/records")

    assert response.status_code == 200
    records_by_id = {record["id"]: record["fields"] for record in response.json()["records"]}
    assert records_by_id["message:message-review"] == {
        "review_id": "message:message-review",
        "review_source": "message",
        "customer_id": "customer-1",
        "message_id": "message-review",
        "reason": "low_confidence",
        "last_error_code": "low_confidence",
        "trace_id": "tg:review",
        "created_at": "2026-07-07T02:00:00+00:00",
    }
    assert records_by_id["draft:draft-review"] == {
        "review_id": "draft:draft-review",
        "review_source": "service_draft",
        "customer_id": "customer-1",
        "message_id": "message-review",
        "draft_id": "draft-review",
        "reason": "sensitive payment data detected",
        "risk_flags": ["sensitive_payment_data_detected"],
        "trace_id": "tg:review",
        "created_at": "2026-07-07T02:02:00+00:00",
    }
    assert records_by_id["agent_run:run-failed"] == {
        "review_id": "agent_run:run-failed",
        "review_source": "agent_run",
        "customer_id": "customer-2",
        "message_id": "message-failed",
        "agent_run_id": "run-failed",
        "reason": "OpenRouter request timed out",
        "last_error_code": "openrouter_timeout",
        "trace_id": "tg:failed-run",
        "created_at": "2026-07-07T02:03:00+00:00",
    }


def test_customer_reply_send_request_view_scopes_and_masks_for_sales() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "service_drafts",
        record_id="draft-customer-1",
        fields={"customer_id": "customer-1", "trace_id": "tg:customer-1"},
    )
    data_source.add_record(
        "service_drafts",
        record_id="draft-customer-2",
        fields={"customer_id": "customer-2", "trace_id": "tg:customer-2"},
    )
    data_source.add_record(
        "telegram_send_requests",
        record_id="send-customer-1",
        fields={
            "source_service_draft_id": "draft-customer-1",
            "send_purpose": "customer_reply_rehearsal",
            "target_chat_id": "customer-chat-secret",
            "status": "sent",
            "requested_by_actor_id": "manager-1",
            "confirmed_by_actor_id": "manager-2",
            "telegram_response_summary": {"ok": True, "message_id": 123},
            "last_error_code": None,
            "sent_at": "2026-07-07T03:00:00+00:00",
            "trace_id": "reply-send:draft-customer-1",
        },
    )
    data_source.add_record(
        "telegram_send_requests",
        record_id="send-customer-2",
        fields={
            "source_service_draft_id": "draft-customer-2",
            "send_purpose": "customer_reply_rehearsal",
            "status": "sent",
            "telegram_response_summary": {"ok": True},
            "trace_id": "reply-send:draft-customer-2",
        },
    )
    data_source.add_record(
        "telegram_send_requests",
        record_id="send-stage04-test",
        fields={
            "send_purpose": "test_send",
            "status": "sent",
            "telegram_response_summary": {"ok": True},
            "trace_id": "tg-send:test",
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
        response = client.get("/views/customer_reply_send_requests/records")

    assert response.status_code == 200
    assert response.json()["records"] == [
        {
            "id": "send-customer-1",
            "fields": {
                "request_id": "send-customer-1",
                "source_service_draft_id": "draft-customer-1",
                "status": "sent",
                "requested_by_actor_id": "manager-1",
                "confirmed_by_actor_id": "manager-2",
                "telegram_response_summary": "[masked]",
                "last_error_code": None,
                "sent_at": "2026-07-07T03:00:00+00:00",
                "trace_id": "reply-send:draft-customer-1",
            },
        }
    ]


def test_stage05_inbox_and_inventory_views_show_agent_evidence() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "messages",
        record_id="message-1",
        fields={
            "telegram_update_id": "update-1",
            "telegram_chat_id": "chat-1",
            "telegram_message_id": "telegram-message-1",
            "telegram_user_id": "user-1",
            "customer_id": "customer-1",
            "binding_status": "bound",
            "message_type": "text",
            "normalized_text": "account blocked",
            "processing_status": "processed",
            "outbox_status": "processed",
            "last_error_code": None,
            "intent_status": "routed",
            "intent_type": "account_status_exception",
            "received_at": "2026-07-07T04:00:00+00:00",
            "trace_id": "tg:message-1",
        },
    )
    data_source.add_record(
        "service_drafts",
        record_id="draft-1",
        fields={"source_message_id": "message-1", "customer_id": "customer-1"},
    )
    data_source.add_record(
        "service_drafts",
        record_id="draft-2",
        fields={"source_message_id": "message-1", "customer_id": "customer-1"},
    )
    data_source.add_record(
        "agent_runs",
        record_id="run-latest",
        fields={
            "message_id": "message-1",
            "status": "failed",
            "error_code": "router_timeout",
            "started_at": "2026-07-07T04:02:00+00:00",
        },
    )
    data_source.add_record(
        "account_inventory",
        record_id="inventory-1",
        fields={
            "platform": "meta",
            "external_account_id": "act_2001",
            "inventory_status": "risk_controlled",
            "assigned_customer_id": "customer-1",
            "assigned_at": "2026-07-07T04:03:00+00:00",
            "status_reason": "customer message says account is risk controlled",
            "trace_id": "account:inventory-1",
        },
    )
    data_source.add_record(
        "account_status_events",
        record_id="status-event-1",
        fields={
            "account_inventory_id": "inventory-1",
            "customer_id": "customer-1",
            "event_type": "risk_controlled",
            "source_entity_type": "message",
            "source_entity_id": "message-1",
            "created_at": "2026-07-07T04:04:00+00:00",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="manager-1",
        role="manager",
    )

    with TestClient(app) as client:
        inbox_response = client.get("/views/telegram_inbox/records")
        inventory_response = client.get("/views/account_inventory/records")

    assert inbox_response.status_code == 200
    assert inbox_response.json()["records"][0]["fields"] == {
        "message_id": "message-1",
        "telegram_update_id": "update-1",
        "telegram_chat_id": "chat-1",
        "telegram_message_id": "telegram-message-1",
        "telegram_user_id": "user-1",
        "customer_id": "customer-1",
        "binding_status": "bound",
        "message_type": "text",
        "text_preview": "account blocked",
        "processing_status": "processed",
        "outbox_status": "processed",
        "last_error_code": None,
        "intent_status": "routed",
        "intent_type": "account_status_exception",
        "agent_status": "failed",
        "draft_count": 2,
        "agent_last_error_code": "router_timeout",
        "received_at": "2026-07-07T04:00:00+00:00",
        "trace_id": "tg:message-1",
    }
    assert inventory_response.status_code == 200
    assert inventory_response.json()["records"][0]["fields"] == {
        "platform": "meta",
        "external_account_id": "act_2001",
        "inventory_status": "risk_controlled",
        "assigned_customer_id": "customer-1",
        "assigned_at": "2026-07-07T04:03:00+00:00",
        "status_reason": "customer message says account is risk controlled",
        "last_risk_signal_at": "2026-07-07T04:04:00+00:00",
        "last_risk_source": "message",
        "trace_id": "account:inventory-1",
    }


def test_stage05_account_inventory_masks_external_id_for_scoped_actor() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "account_inventory",
        record_id="inventory-customer-1",
        fields={
            "platform": "meta",
            "external_account_id": "act_customer_1_secret",
            "inventory_status": "allocated",
            "assigned_customer_id": "customer-1",
            "trace_id": "account:customer-1",
        },
    )
    data_source.add_record(
        "account_inventory",
        record_id="inventory-customer-2",
        fields={
            "platform": "meta",
            "external_account_id": "act_customer_2_secret",
            "inventory_status": "allocated",
            "assigned_customer_id": "customer-2",
            "trace_id": "account:customer-2",
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
        response = client.get("/views/account_inventory/records")

    assert response.status_code == 200
    assert response.json()["records"] == [
        {
            "id": "inventory-customer-1",
            "fields": {
                "platform": "meta",
                "external_account_id": "[masked]",
                "inventory_status": "allocated",
                "assigned_customer_id": "customer-1",
                "trace_id": "account:customer-1",
            },
        }
    ]
