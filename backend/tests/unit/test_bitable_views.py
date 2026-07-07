from fastapi.testclient import TestClient

from app.api.deps import get_system_actor
from app.api.routes.views import get_bitable_view_data_source
from app.main import create_app
from app.services.bitable_views import (
    EmptyBitableViewDataSource,
    InMemoryBitableViewDataSource,
    SqlAlchemyBitableViewDataSource,
    mask_record_fields,
)
from app.services.permissions import Actor


class FakeRowMapping:
    def __init__(self, values: dict) -> None:
        self._mapping = values


class FakeQueryResult:
    def __init__(self, rows: list[FakeRowMapping]) -> None:
        self.rows = rows

    def all(self) -> list[FakeRowMapping]:
        return self.rows


class FakeSqlAlchemySession:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.statements: list[object] = []

    def execute(self, statement):
        self.statements.append(statement)
        return FakeQueryResult([FakeRowMapping(row) for row in self.rows])


def test_known_view_returns_table_shape() -> None:
    app = create_app()
    app.dependency_overrides[get_bitable_view_data_source] = (
        lambda: EmptyBitableViewDataSource()
    )

    with TestClient(app) as client:
        response = client.get("/views/telegram_inbox/records")

        assert response.status_code == 200
        assert response.json() == {
            "view_key": "telegram_inbox",
            "records": [],
            "trace_id": "view:telegram_inbox",
        }


def test_unknown_view_returns_stable_error() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/views/not_real/records")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "unknown_view"


def test_default_view_dependency_uses_sqlalchemy_data_source() -> None:
    session = FakeSqlAlchemySession(rows=[])

    data_source = get_bitable_view_data_source(session=session)

    assert isinstance(data_source, SqlAlchemyBitableViewDataSource)
    assert data_source.session is session


def test_mask_record_fields_masks_not_allowed_fields() -> None:
    record = {
        "id": "message-1",
        "fields": {
            "intent_status": "unclassified",
            "raw_text": "customer secret",
        },
    }

    masked = mask_record_fields(record, allowed_fields={"intent_status"})

    assert masked == {
        "id": "message-1",
        "fields": {
            "intent_status": "unclassified",
            "raw_text": "[masked]",
        },
    }


def test_view_api_projects_telegram_inbox_stage03_fields() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "messages",
        record_id="message-1",
        fields={
            "telegram_update_id": "update-1",
            "telegram_chat_id": "chat-1",
            "telegram_user_id": "user-1",
            "customer_id": "customer-1",
            "binding_status": "bound",
            "message_type": "text",
            "normalized_text": "customer preview",
            "processing_status": "queued",
            "outbox_status": "pending",
            "last_error_code": None,
            "received_at": "2026-07-04T09:00:00+00:00",
            "processed_at": None,
            "raw_text": "customer secret recharge request",
            "ignored_field": "not part of this view",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source

    with TestClient(app) as client:
        response = client.get("/views/telegram_inbox/records")

    assert response.status_code == 200
    assert response.json()["records"] == [
            {
                "id": "message-1",
                "fields": {
                    "message_id": "message-1",
                    "telegram_update_id": "update-1",
                    "telegram_chat_id": "chat-1",
                    "telegram_user_id": "user-1",
                    "customer_id": "customer-1",
                    "binding_status": "bound",
                    "message_type": "text",
                    "text_preview": "customer preview",
                    "processing_status": "queued",
                    "outbox_status": "pending",
                    "last_error_code": None,
                    "received_at": "2026-07-04T09:00:00+00:00",
                    "processed_at": None,
                },
            }
        ]


def test_account_inventory_view_projects_assignment_and_status_fields() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "account_inventory",
        record_id="inventory-1",
        fields={
            "platform": "meta",
            "external_account_id": "act_2001",
            "inventory_status": "allocated",
            "assigned_customer_id": "customer-1",
            "assigned_at": "2026-07-04T09:00:00+00:00",
            "status_reason": "assigned after confirmation",
            "ignored_field": "not part of this view",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source

    with TestClient(app) as client:
        response = client.get("/views/account_inventory/records")

    assert response.status_code == 200
    assert response.json()["records"] == [
        {
            "id": "inventory-1",
                "fields": {
                    "platform": "meta",
                    "external_account_id": "act_2001",
                    "inventory_status": "allocated",
                    "assigned_customer_id": "customer-1",
                    "assigned_at": "2026-07-04T09:00:00+00:00",
                "status_reason": "assigned after confirmation",
            },
        }
    ]


def test_card_binding_views_mask_sensitive_card_fields() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "payment_profiles",
        record_id="profile-1",
        fields={
            "provider": "stripe",
            "tokenized_profile_id": "tok_sensitive",
            "masked_label": "Visa **** 4242",
            "last4": "4242",
            "brand": "visa",
            "status": "active",
        },
    )
    data_source.add_record(
        "account_card_bindings",
        record_id="binding-1",
        fields={
            "account_asset_id": "account-1",
            "payment_profile_id": "profile-1",
            "customer_id": "customer-1",
            "binding_status": "failed",
            "one_card_one_account_policy": "strict",
            "failure_reason": "provider timeout",
            "trace_id": "binding:account-1",
        },
    )
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source

    with TestClient(app) as client:
        profile_response = client.get("/views/payment_profiles/records")
        binding_response = client.get("/views/account_card_bindings/records")

    assert profile_response.status_code == 200
    assert profile_response.json()["records"][0]["fields"] == {
        "provider": "stripe",
        "tokenized_profile_id": "[masked]",
        "masked_label": "Visa **** 4242",
        "last4": "4242",
        "brand": "visa",
        "status": "active",
    }
    assert binding_response.status_code == 200
    assert binding_response.json()["records"][0]["fields"] == {
        "account_asset_id": "account-1",
        "payment_profile_id": "[masked]",
        "customer_id": "customer-1",
        "binding_status": "failed",
        "one_card_one_account_policy": "strict",
        "failure_reason": "[masked]",
        "trace_id": "binding:account-1",
    }


def test_view_api_applies_actor_record_scope_and_field_permissions() -> None:
    app = create_app()
    data_source = InMemoryBitableViewDataSource()
    data_source.add_record(
        "recharge_records",
        record_id="recharge-1",
        fields={
            "customer_id": "customer-1",
            "amount": 1000,
            "currency": "USD",
            "collection_status": "confirmed",
            "execution_status": "succeeded",
            "readback_status": "failed",
        },
    )
    data_source.add_record(
        "recharge_records",
        record_id="recharge-2",
        fields={
            "customer_id": "customer-2",
            "amount": 2000,
            "currency": "USD",
            "collection_status": "pending",
            "execution_status": "succeeded",
            "readback_status": "pending",
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
        response = client.get("/views/recharge_view/records")

    assert response.status_code == 200
    assert response.json()["records"] == [
        {
            "id": "recharge-1",
            "fields": {
                "customer_id": "customer-1",
                "amount": "[masked]",
                "currency": "USD",
                "collection_status": "confirmed",
                "execution_status": "succeeded",
                "readback_status": "failed",
            },
        }
    ]


def test_sqlalchemy_bitable_data_source_reads_metadata_table_rows() -> None:
    session = FakeSqlAlchemySession(
        rows=[
            {
                "id": "message-1",
                "telegram_chat_id": "chat-1",
                "telegram_message_id": "message-1",
                "message_type": "text",
                "intent_status": "routed",
                "intent_type": "recharge",
                "received_at": "2026-07-04T09:00:00+00:00",
                "trace_id": "tg:update-1",
                "raw_text": "customer secret",
            }
        ]
    )
    data_source = SqlAlchemyBitableViewDataSource(session=session)

    records = data_source.list_records("messages")

    assert len(session.statements) == 1
    assert records == [
        {
            "id": "message-1",
            "fields": {
                "telegram_chat_id": "chat-1",
                "telegram_message_id": "message-1",
                "message_type": "text",
                "intent_status": "routed",
                "intent_type": "recharge",
                "received_at": "2026-07-04T09:00:00+00:00",
                "trace_id": "tg:update-1",
                "raw_text": "customer secret",
            },
        }
    ]


def test_sqlalchemy_bitable_data_source_returns_empty_for_unknown_table() -> None:
    session = FakeSqlAlchemySession(rows=[])
    data_source = SqlAlchemyBitableViewDataSource(session=session)

    records = data_source.list_records("not_a_table")

    assert records == []
    assert session.statements == []


def test_every_stage_02_view_can_return_workflow_records() -> None:
    data_source = InMemoryBitableViewDataSource()
    for view_key, table_name in {
        "telegram_inbox": "messages",
        "ai_draft_queue": "service_drafts",
        "recharge_view": "recharge_records",
        "account_inventory": "account_inventory",
        "payment_profiles": "payment_profiles",
        "account_card_bindings": "account_card_bindings",
        "customer_daily_reports": "customer_daily_reports",
        "company_daily_reports": "company_daily_reports",
        "audit_view": "ops_audit_events",
    }.items():
        data_source.add_record(
            table_name,
            record_id=f"{table_name}-1",
            fields={"trace_id": f"trace:{view_key}", "status": "visible"},
        )

    app = create_app()
    app.dependency_overrides[get_bitable_view_data_source] = lambda: data_source

    with TestClient(app) as client:
        for view_key in {
            "telegram_inbox",
            "ai_draft_queue",
            "recharge_view",
            "account_inventory",
            "payment_profiles",
            "account_card_bindings",
            "customer_daily_reports",
            "company_daily_reports",
            "audit_view",
        }:
            response = client.get(f"/views/{view_key}/records")
            assert response.status_code == 200
            assert response.json()["records"], view_key
