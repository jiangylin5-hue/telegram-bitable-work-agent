import os
from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_system_actor
from app.core.database import get_session
from app.main import create_app
from app.models.accounts import AccountAsset, AccountInventory, AccountStatusEvent
from app.models.audit import OpsAuditEvent
from app.models.cards import AccountCardBinding, PaymentProfile
from app.models.customers import Customer, CustomerGroup
from app.models.outbox import OutboxEvent
from app.models.recharge import CollectionRecord, RechargeRecord
from app.models.reporting import (
    AccountDailyMetric,
    CompanyDailyReport,
    CustomerDailyReport,
    RiskEvent,
)
from app.models.service import ExecutionTicket, ServiceRecord
from app.models.service_drafts import ServiceDraft
from app.models.telegram import Message
from app.repositories.outbox import SqlAlchemyOutboxRepository
from app.services.account_inventory import (
    SqlAlchemyAccountInventoryUnitOfWork,
    confirm_account_assignment,
    create_inventory_account,
    propose_account_assignment,
)
from app.services.permissions import Actor
from app.services.recharge import (
    SqlAlchemyRechargeUnitOfWork,
    confirm_collection,
    create_collection_record_for_recharge,
    create_recharge_record_from_confirmation,
    execute_recharge_with_mock_provider,
    mark_readback_failed,
)
from app.services.service_drafts import SqlAlchemyServiceDraftUnitOfWork
from app.workers.handlers import handle_agent_intent_extract
from app.workers.outbox_dispatcher import OutboxDispatcher, RetryableOutboxError


ONLINE_DATABASE_URL_ENV = "STAGE02_ONLINE_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not os.getenv(ONLINE_DATABASE_URL_ENV),
    reason=f"{ONLINE_DATABASE_URL_ENV} is required for online PostgreSQL smoke tests",
)


@dataclass(frozen=True)
class OnlineDatabase:
    engine: Engine
    session_factory: sessionmaker[Session]


@pytest.fixture()
def online_db(monkeypatch: pytest.MonkeyPatch) -> Generator[OnlineDatabase, None, None]:
    database_url = os.environ[ONLINE_DATABASE_URL_ENV]
    _assert_disposable_database_url(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = create_engine(database_url, future=True, pool_pre_ping=True)
    _reset_public_schema(engine)
    command.upgrade(_alembic_config(database_url), "head")

    try:
        yield OnlineDatabase(
            engine=engine,
            session_factory=sessionmaker(
                bind=engine,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
            ),
        )
    finally:
        engine.dispose()


def test_online_alembic_upgrade_creates_stage02_fact_tables(
    online_db: OnlineDatabase,
) -> None:
    inspector = inspect(online_db.engine)

    assert {
        "messages",
        "service_drafts",
        "service_records",
        "execution_tickets",
        "outbox_events",
        "ops_audit_events",
        "account_inventory",
        "customer_daily_reports",
        "company_daily_reports",
        "telegram_customer_bindings",
    }.issubset(set(inspector.get_table_names()))

    with online_db.engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == (
            "20260728_0034"
        )


def test_online_postgres_api_write_is_visible_in_bitable_view(
    online_db: OnlineDatabase,
) -> None:
    customer_id = uuid4()
    _seed_customer_group(
        online_db.session_factory,
        customer_id=customer_id,
        telegram_chat_id="stage02-online-chat",
    )

    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)

    with TestClient(app) as client:
        ingest_response = client.post(
            "/mock/telegram/updates",
            json={
                "update_id": "stage02-online-update-1",
                "chat_id": "stage02-online-chat",
                "message_id": "stage02-online-message-1",
                "sender_user_id": "customer-online-user",
                "username": "customer_online",
                "text": "recharge act_online_1001 100 USD",
            },
        )
        view_response = client.get("/views/telegram_inbox/records")

    assert ingest_response.status_code == 200
    message_id = ingest_response.json()["message_id"]
    assert view_response.status_code == 200
    records = view_response.json()["records"]
    matching_records = [record for record in records if record["id"] == message_id]
    assert matching_records == [
        {
            "id": message_id,
            "fields": {
                "message_id": message_id,
                "telegram_update_id": "stage02-online-update-1",
                "telegram_chat_id": "stage02-online-chat",
                "telegram_message_id": "stage02-online-message-1",
                "telegram_user_id": "customer-online-user",
                "customer_id": str(customer_id),
                "binding_status": "bound",
                "message_type": "text",
                "text_preview": "recharge act_online_1001 100 USD",
                "processing_status": "queued",
                "outbox_status": "pending",
                "last_error_code": None,
                "intent_status": "unclassified",
                "intent_type": None,
                "received_at": matching_records[0]["fields"]["received_at"],
                "processed_at": None,
                "trace_id": "tg:stage02-online-update-1",
            },
        }
    ]

    with online_db.session_factory() as session:
        stored_message = session.get(Message, UUID(message_id))
        assert stored_message is not None
        assert stored_message.customer_id == customer_id
        assert _count(session, OutboxEvent) == 1
        assert _count(session, OpsAuditEvent) == 2


def test_online_audit_view_reads_real_audit_events(
    online_db: OnlineDatabase,
) -> None:
    customer_id = uuid4()
    _seed_customer_group(
        online_db.session_factory,
        customer_id=customer_id,
        telegram_chat_id="stage02-online-audit-chat",
    )

    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)

    with TestClient(app) as client:
        ingest_response = client.post(
            "/mock/telegram/updates",
            json={
                "update_id": "stage02-online-audit-update-1",
                "chat_id": "stage02-online-audit-chat",
                "message_id": "stage02-online-audit-message-1",
                "sender_user_id": "customer-online-user",
                "username": "customer_online",
                "text": "recharge act_online_audit 100 USD",
            },
        )
        audit_view_response = client.get("/views/audit_view/records")

    assert ingest_response.status_code == 200
    assert audit_view_response.status_code == 200
    records = audit_view_response.json()["records"]
    matching_records = [
        record
        for record in records
        if record["fields"]["trace_id"] == "tg:stage02-online-audit-update-1"
    ]
    assert len(matching_records) == 2
    assert {
        (record["fields"]["actor_type"], record["fields"]["event_type"])
        for record in matching_records
    } == {
        ("telegram", "message_ingested"),
        ("system", "telegram.binding.resolved"),
    }
    assert all(
        record["fields"]["entity_type"] == "message"
        and record["fields"]["created_at"]
        for record in matching_records
    )

    with online_db.session_factory() as session:
        audit_event = session.scalar(
            select(OpsAuditEvent).where(
                OpsAuditEvent.trace_id == "tg:stage02-online-audit-update-1"
            )
        )
        assert audit_event is not None
        assert str(audit_event.id) in {record["id"] for record in matching_records}


def test_online_mock_telegram_duplicate_update_is_idempotent_across_sessions(
    online_db: OnlineDatabase,
) -> None:
    customer_id = uuid4()
    _seed_customer_group(
        online_db.session_factory,
        customer_id=customer_id,
        telegram_chat_id="stage02-online-duplicate-chat",
    )

    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)
    payload = {
        "update_id": "stage02-online-duplicate-update-1",
        "chat_id": "stage02-online-duplicate-chat",
        "message_id": "stage02-online-duplicate-message-1",
        "sender_user_id": "customer-online-user",
        "username": "customer_online",
        "text": "recharge act_online_dup 100 USD",
    }

    with TestClient(app) as client:
        first_response = client.post("/mock/telegram/updates", json=payload)
        second_response = client.post("/mock/telegram/updates", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["status"] == "stored"
    assert second_response.json()["status"] == "duplicate"
    assert second_response.json()["message_id"] == first_response.json()["message_id"]

    with online_db.session_factory() as session:
        assert _count(session, Message) == 1
        assert _count(session, OutboxEvent) == 1
        assert _count(session, OpsAuditEvent) == 2


def test_online_agent_intent_extract_uses_database_uow_and_updates_draft_view(
    online_db: OnlineDatabase,
) -> None:
    customer_id = uuid4()
    _seed_customer_group(
        online_db.session_factory,
        customer_id=customer_id,
        telegram_chat_id="stage02-online-agent-chat",
    )

    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)

    with TestClient(app) as client:
        ingest_response = client.post(
            "/mock/telegram/updates",
            json={
                "update_id": "stage02-online-agent-update-1",
                "chat_id": "stage02-online-agent-chat",
                "message_id": "stage02-online-agent-message-1",
                "sender_user_id": "customer-online-user",
                "username": "customer_online",
                "text": "recharge act_online_2001 200 USD",
            },
        )

    assert ingest_response.status_code == 200
    message_id = UUID(ingest_response.json()["message_id"])

    with online_db.session_factory.begin() as session:
        event = session.scalar(
            select(OutboxEvent).where(OutboxEvent.event_type == "agent.intent_extract")
        )
        assert event is not None
        handle_agent_intent_extract(event, SqlAlchemyServiceDraftUnitOfWork(session))

    with TestClient(app) as client:
        inbox_response = client.get("/views/telegram_inbox/records")
        draft_response = client.get("/views/ai_draft_queue/records")

    assert inbox_response.status_code == 200
    inbox_record = next(
        record
        for record in inbox_response.json()["records"]
        if record["id"] == str(message_id)
    )
    assert inbox_record["fields"]["intent_status"] == "routed"
    assert inbox_record["fields"]["intent_type"] == "recharge"

    assert draft_response.status_code == 200
    draft_records = draft_response.json()["records"]
    assert len(draft_records) == 1
    assert draft_records[0]["fields"] == {
        "status": "pending_confirmation",
        "intent_type": "recharge",
        "customer_id": str(customer_id),
        "trace_id": "tg:stage02-online-agent-update-1",
    }

    with online_db.session_factory() as session:
        stored_message = session.get(Message, message_id)
        assert stored_message.intent_status == "routed"
        assert stored_message.intent_type == "recharge"
        draft = session.scalar(select(ServiceDraft))
        assert draft is not None
        assert draft.source_message_id == message_id
        assert draft.payload == {
            "account_id": "act_online_2001",
            "amount": "200",
            "currency": "USD",
        }
        assert _count(session, OpsAuditEvent) == 3


def test_online_confirmation_route_commits_service_record_ticket_and_view_state(
    online_db: OnlineDatabase,
) -> None:
    actor_id = uuid4()
    customer_id = uuid4()
    draft_id = _seed_pending_service_draft(
        online_db.session_factory,
        customer_id=customer_id,
    )

    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)

    with TestClient(app) as client:
        confirm_response = client.post(
            f"/confirmations/service-drafts/{draft_id}/actions",
            json={
                "action": "confirm",
                "actor_type": "user",
                "actor_id": str(actor_id),
                "role": "production",
            },
        )
        view_response = client.get("/views/ai_draft_queue/records")

    assert confirm_response.status_code == 200
    assert confirm_response.json()["draft_status"] == "confirmed"
    assert confirm_response.json()["service_record_id"] is not None
    assert confirm_response.json()["execution_ticket_id"] is not None

    with online_db.session_factory() as session:
        draft = session.get(ServiceDraft, draft_id)
        assert draft is not None
        assert draft.status == "confirmed"
        assert _count(session, ServiceRecord) == 1
        assert _count(session, ExecutionTicket) == 1
        assert _count(session, OpsAuditEvent) == 1

    assert view_response.status_code == 200
    matching_records = [
        record
        for record in view_response.json()["records"]
        if record["id"] == str(draft_id)
    ]
    assert matching_records == [
        {
            "id": str(draft_id),
            "fields": {
                "status": "confirmed",
                "intent_type": "recharge",
                "customer_id": str(customer_id),
                "trace_id": f"draft:{draft_id}",
            },
        }
    ]


def test_online_agent_confirmation_denial_persists_audit_without_business_writes(
    online_db: OnlineDatabase,
) -> None:
    customer_id = uuid4()
    draft_id = _seed_pending_service_draft(
        online_db.session_factory,
        customer_id=customer_id,
    )

    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)

    with TestClient(app) as client:
        deny_response = client.post(
            f"/confirmations/service-drafts/{draft_id}/actions",
            json={
                "action": "confirm",
                "actor_type": "agent",
                "actor_id": "mock_router",
                "role": "agent",
            },
        )
        draft_view_response = client.get("/views/ai_draft_queue/records")
        audit_view_response = client.get("/views/audit_view/records")

    assert deny_response.status_code == 403
    assert deny_response.json()["detail"] == "agent cannot perform confirm_draft"

    with online_db.session_factory() as session:
        draft = session.get(ServiceDraft, draft_id)
        assert draft is not None
        assert draft.status == "pending_confirmation"
        assert _count(session, ServiceRecord) == 0
        assert _count(session, ExecutionTicket) == 0
        audit_event = session.scalar(
            select(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "permission_denied"
            )
        )
        assert audit_event is not None
        assert audit_event.trace_id == f"draft:{draft_id}"
        assert audit_event.entity_id == draft_id
        assert audit_event.permission_snapshot == {
            "action": "confirm_draft",
            "role": "agent",
            "actor_type": "agent",
        }

    assert draft_view_response.status_code == 200
    matching_draft_records = [
        record
        for record in draft_view_response.json()["records"]
        if record["id"] == str(draft_id)
    ]
    assert matching_draft_records == [
        {
            "id": str(draft_id),
            "fields": {
                "status": "pending_confirmation",
                "intent_type": "recharge",
                "customer_id": str(customer_id),
                "trace_id": f"draft:{draft_id}",
            },
        }
    ]

    assert audit_view_response.status_code == 200
    matching_audit_records = [
        record
        for record in audit_view_response.json()["records"]
        if record["fields"]["trace_id"] == f"draft:{draft_id}"
    ]
    assert matching_audit_records == [
        {
            "id": matching_audit_records[0]["id"],
            "fields": {
                "trace_id": f"draft:{draft_id}",
                "actor_type": "agent",
                "event_type": "permission_denied",
                "entity_type": "service_draft",
                "created_at": matching_audit_records[0]["fields"]["created_at"],
            },
        }
    ]


def test_online_business_write_and_outbox_event_rollback_atomically(
    online_db: OnlineDatabase,
) -> None:
    draft_id = uuid4()
    outbox_id = uuid4()
    customer_id = _seed_customer(online_db.session_factory)

    with online_db.session_factory() as session:
        draft = ServiceDraft(
            id=draft_id,
            draft_type="recharge",
            status="pending_confirmation",
            customer_id=customer_id,
            created_by_type="agent",
            created_by_id="mock_router",
            payload={"amount": "100.00", "currency": "USD"},
            missing_fields=[],
            risk_flags=[],
            confidence="0.9000",
            trace_id=f"draft:{draft_id}",
            idempotency_key=f"draft:{draft_id}:rollback",
        )
        event = OutboxEvent(
            id=outbox_id,
            event_type="execution.recharge",
            aggregate_type="service_draft",
            aggregate_id=str(draft_id),
            payload={"draft_id": str(draft_id)},
            status="pending",
            attempts=0,
            attempt_count=0,
            max_attempts=3,
            idempotency_key=f"execution:{draft_id}:rollback",
            trace_id=f"draft:{draft_id}",
        )
        session.add(draft)
        session.add(event)
        session.flush()

        assert session.get(ServiceDraft, draft_id) is draft
        assert session.get(OutboxEvent, outbox_id) is event

        session.rollback()

    with online_db.session_factory() as session:
        assert session.get(ServiceDraft, draft_id) is None
        assert session.get(OutboxEvent, outbox_id) is None


def test_online_reporting_routes_read_facts_commit_reports_and_update_views(
    online_db: OnlineDatabase,
) -> None:
    report_date = date(2026, 7, 4)
    customer_id, account_asset_id = _seed_reporting_facts(
        online_db.session_factory,
        report_date=report_date,
    )
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)

    with TestClient(app) as client:
        customer_response = client.post(
            f"/reports/customer-daily/{customer_id}",
            params={"report_date": report_date.isoformat()},
        )
        company_response = client.post(
            "/reports/company-daily",
            params={"report_date": report_date.isoformat()},
        )
        customer_view_response = client.get("/views/customer_daily_reports/records")
        company_view_response = client.get("/views/company_daily_reports/records")

    assert customer_response.status_code == 200
    assert company_response.status_code == 200
    customer_payload = customer_response.json()["report_payload"]
    company_payload = company_response.json()["report_payload"]
    assert customer_payload["metrics"][0]["account_asset_id"] == str(account_asset_id)
    assert customer_payload["recharge_records"][0]["amount"] == "250.00"
    assert customer_payload["card_binding_state"]["status"] == "available"
    assert company_payload["total_spend_by_currency"] == {"USD": "41.50"}
    assert company_payload["recharge_summary"]["amount_by_currency"] == {
        "USD": "250.00"
    }
    assert company_payload["card_binding_summary"]["status_counts"] == {"bound": 1}

    with online_db.session_factory() as session:
        assert _count(session, CustomerDailyReport) == 1
        assert _count(session, CompanyDailyReport) == 1
        assert _count(session, OpsAuditEvent) == 2

    assert customer_view_response.status_code == 200
    assert customer_view_response.json()["records"][0]["fields"]["delivery_status"] == (
        "draft"
    )
    assert company_view_response.status_code == 200
    assert company_view_response.json()["records"][0]["fields"]["delivery_status"] == (
        "draft"
    )


def test_online_customer_report_keeps_stale_spend_unknown_and_persists_risk_event(
    online_db: OnlineDatabase,
) -> None:
    report_date = date(2026, 7, 4)
    customer_id, metric_id = _seed_stale_reporting_metric(
        online_db.session_factory,
        report_date=report_date,
    )
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)

    with TestClient(app) as client:
        response = client.post(
            f"/reports/customer-daily/{customer_id}",
            params={"report_date": report_date.isoformat()},
        )
        view_response = client.get("/views/customer_daily_reports/records")

    assert response.status_code == 200
    payload = response.json()["report_payload"]
    report_metric = payload["metrics"][0]
    assert report_metric["read_status"] == "stale_data"
    assert report_metric["spend"]["amount"] is None
    assert payload["risk_events"][0]["risk_type"] == "stale_data"
    assert payload["risk_events"][0]["source_metric_id"] == str(metric_id)

    with online_db.session_factory() as session:
        assert _count(session, CustomerDailyReport) == 1
        assert _count(session, RiskEvent) == 1
        risk_event = session.scalar(select(RiskEvent))
        assert risk_event is not None
        assert risk_event.risk_type == "stale_data"
        assert risk_event.source_metric_id == metric_id
        audit_types = [
            row[0]
            for row in session.execute(
                select(OpsAuditEvent.event_type).order_by(OpsAuditEvent.created_at)
            )
        ]
        assert audit_types == [
            "risk_event_created",
            "customer_daily_report_generated",
        ]

    assert view_response.status_code == 200
    view_payload = view_response.json()["records"][0]["fields"]["report_payload"]
    assert view_payload["metrics"][0]["read_status"] == "stale_data"
    assert view_payload["metrics"][0]["spend"]["amount"] is None
    assert view_payload["risk_events"][0]["risk_type"] == "stale_data"


def test_online_customer_report_api_denies_unscoped_sales_and_persists_audit(
    online_db: OnlineDatabase,
) -> None:
    report_date = date(2026, 7, 4)
    customer_id, _ = _seed_reporting_facts(
        online_db.session_factory,
        report_date=report_date,
    )
    sales_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="sales",
        customer_ids=frozenset({str(uuid4())}),
    )
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)
    app.dependency_overrides[get_system_actor] = lambda: sales_actor

    with TestClient(app, raise_server_exceptions=False) as client:
        deny_response = client.post(
            f"/reports/customer-daily/{customer_id}",
            params={"report_date": report_date.isoformat()},
        )
        app.dependency_overrides[get_system_actor] = lambda: Actor(
            actor_type="system",
            actor_id="stage-02-system",
            role="admin",
        )
        audit_view_response = client.get("/views/audit_view/records")

    assert deny_response.status_code == 403
    assert deny_response.json()["detail"] == f"sales cannot view customer {customer_id}"

    with online_db.session_factory() as session:
        assert _count(session, CustomerDailyReport) == 0
        audit_event = session.scalar(
            select(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "permission_denied"
            )
        )
        assert audit_event is not None
        assert audit_event.trace_id == (
            f"report:customer:{customer_id}:{report_date.isoformat()}"
        )
        assert audit_event.entity_type == "customer_daily_report"
        assert audit_event.entity_id is None
        assert audit_event.permission_snapshot == {
            "action": "view_customer_report",
            "role": "sales",
            "actor_type": "user",
            "customer_id": str(customer_id),
        }

    assert audit_view_response.status_code == 200
    matching_audit_records = [
        record
        for record in audit_view_response.json()["records"]
        if record["fields"]["trace_id"]
        == f"report:customer:{customer_id}:{report_date.isoformat()}"
    ]
    assert matching_audit_records == [
        {
            "id": matching_audit_records[0]["id"],
            "fields": {
                "trace_id": (
                    f"report:customer:{customer_id}:{report_date.isoformat()}"
                ),
                "actor_type": "user",
                "event_type": "permission_denied",
                "entity_type": "customer_daily_report",
                "created_at": matching_audit_records[0]["fields"]["created_at"],
            },
        }
    ]


def test_online_company_report_api_denies_sales_and_persists_audit(
    online_db: OnlineDatabase,
) -> None:
    report_date = date(2026, 7, 4)
    customer_id, _ = _seed_reporting_facts(
        online_db.session_factory,
        report_date=report_date,
    )
    sales_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="sales",
        customer_ids=frozenset({str(customer_id)}),
    )
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)
    app.dependency_overrides[get_system_actor] = lambda: sales_actor

    with TestClient(app, raise_server_exceptions=False) as client:
        deny_response = client.post(
            "/reports/company-daily",
            params={"report_date": report_date.isoformat()},
        )
        app.dependency_overrides[get_system_actor] = lambda: Actor(
            actor_type="system",
            actor_id="stage-02-system",
            role="admin",
        )
        audit_view_response = client.get("/views/audit_view/records")

    assert deny_response.status_code == 403
    assert deny_response.json()["detail"] == "sales cannot perform view_company_report"

    with online_db.session_factory() as session:
        assert _count(session, CompanyDailyReport) == 0
        audit_event = session.scalar(
            select(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "permission_denied"
            )
        )
        assert audit_event is not None
        assert audit_event.trace_id == f"report:company:{report_date.isoformat()}"
        assert audit_event.entity_type == "company_daily_report"
        assert audit_event.entity_id is None
        assert audit_event.permission_snapshot == {
            "action": "view_company_report",
            "role": "sales",
            "actor_type": "user",
        }

    assert audit_view_response.status_code == 200
    matching_audit_records = [
        record
        for record in audit_view_response.json()["records"]
        if record["fields"]["trace_id"]
        == f"report:company:{report_date.isoformat()}"
    ]
    assert matching_audit_records == [
        {
            "id": matching_audit_records[0]["id"],
            "fields": {
                "trace_id": f"report:company:{report_date.isoformat()}",
                "actor_type": "user",
                "event_type": "permission_denied",
                "entity_type": "company_daily_report",
                "created_at": matching_audit_records[0]["fields"]["created_at"],
            },
        }
    ]


def test_online_inventory_services_persist_assignment_and_view_status(
    online_db: OnlineDatabase,
) -> None:
    customer_id = _seed_customer(online_db.session_factory)
    production_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="production",
    )
    agent_actor = Actor(
        actor_type="agent",
        actor_id="account-inventory-agent",
        role="agent",
    )

    with online_db.session_factory.begin() as session:
        uow = SqlAlchemyAccountInventoryUnitOfWork(session)
        account = create_inventory_account(
            uow,
            actor=production_actor,
            platform="meta",
            external_account_id="act_online_inventory_1001",
            production_batch_id="stage02-online",
        )
        assignment = propose_account_assignment(
            uow,
            actor=agent_actor,
            account_inventory_id=account.id,
            customer_id=customer_id,
        )
        confirm_account_assignment(
            uow,
            actor=production_actor,
            assignment_id=assignment.id,
        )
        account_id = account.id

    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)
    app.dependency_overrides[get_system_actor] = lambda: Actor(
        actor_type="user",
        actor_id="sales-online",
        role="sales",
        customer_ids=frozenset({str(customer_id)}),
    )
    with TestClient(app) as client:
        inventory_response = client.get(
            f"/inventory/accounts?status=allocated&customer_id={customer_id}"
        )
        view_response = client.get("/views/account_inventory/records")

    assert inventory_response.status_code == 200
    assert inventory_response.json()["records"][0]["id"] == str(account_id)
    assert inventory_response.json()["records"][0]["inventory_status"] == "allocated"
    assert inventory_response.json()["records"][0]["assigned_customer_id"] == (
        str(customer_id)
    )
    assert view_response.status_code == 200
    matching_records = [
        record
        for record in view_response.json()["records"]
        if record["id"] == str(account_id)
    ]
    assert matching_records[0]["fields"]["external_account_id"] == "[masked]"
    assert matching_records[0]["fields"]["inventory_status"] == "allocated"
    assert matching_records[0]["fields"]["assigned_customer_id"] == str(customer_id)

    with online_db.session_factory() as session:
        assert session.get(AccountInventory, account_id).assigned_customer_id == customer_id
        assert _count(session, AccountStatusEvent) == 2
        assert _count(session, OpsAuditEvent) == 2


def test_online_recharge_service_persists_execution_readback_and_view_status(
    online_db: OnlineDatabase,
) -> None:
    service_record_id, ticket_id = _seed_confirmed_recharge_service(
        online_db.session_factory
    )

    with online_db.session_factory.begin() as session:
        uow = SqlAlchemyRechargeUnitOfWork(session)
        recharge = create_recharge_record_from_confirmation(
            uow,
            service_record=session.get(ServiceRecord, service_record_id),
            ticket=session.get(ExecutionTicket, ticket_id),
            amount=Decimal("300.00"),
            currency="USD",
        )
        collection = create_collection_record_for_recharge(
            uow,
            recharge=recharge,
            collection_method="bank",
        )
        confirm_collection(
            uow,
            collection.id,
            confirmed_by_user_id=uuid4(),
        )
        execute_recharge_with_mock_provider(uow, recharge.id)
        mark_readback_failed(
            uow,
            recharge.id,
            error_message="online smoke readback failed",
        )
        recharge_id = recharge.id

    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)
    with TestClient(app) as client:
        view_response = client.get("/views/recharge_view/records")

    assert view_response.status_code == 200
    matching_records = [
        record
        for record in view_response.json()["records"]
        if record["id"] == str(recharge_id)
    ]
    fields = matching_records[0]["fields"]
    assert fields["amount"] in {"300.00", 300, 300.0}
    assert fields["currency"] == "USD"
    assert fields["collection_status"] == "confirmed"
    assert fields["execution_status"] == "succeeded"
    assert fields["readback_status"] == "failed"
    assert fields["readback_at"] is not None
    with online_db.session_factory() as session:
        stored_recharge = session.get(RechargeRecord, recharge_id)
        assert stored_recharge.execution_status == "succeeded"
        assert stored_recharge.readback_status == "failed"
        assert session.get(ExecutionTicket, ticket_id).status == "used"
        assert _count(session, CollectionRecord) == 1
        outbox_events = list(
            session.scalars(
                select(OutboxEvent).order_by(OutboxEvent.event_type)
            )
        )
        assert [event.event_type for event in outbox_events] == [
            "customer.reply",
            "readback.balance",
        ]
        reply_event = outbox_events[0]
        assert reply_event.aggregate_type == "recharge_record"
        assert reply_event.aggregate_id == str(recharge_id)
        assert reply_event.payload["customer_id"] == str(stored_recharge.customer_id)
        assert reply_event.payload["recharge_id"] == str(recharge_id)
        assert reply_event.payload["execution_status"] == "succeeded"
        assert reply_event.payload["readback_status"] == "failed"
        assert "execution succeeded" in reply_event.payload["message_text"]
        assert "balance readback failed" in reply_event.payload["message_text"]
        assert _count(session, OpsAuditEvent) == 5


def test_online_recharge_view_scopes_and_masks_sales_actor_from_real_rows(
    online_db: OnlineDatabase,
) -> None:
    report_date = date(2026, 7, 4)
    scoped_customer_id, _ = _seed_reporting_facts(
        online_db.session_factory,
        report_date=report_date,
    )
    unscoped_customer_id, _ = _seed_reporting_facts(
        online_db.session_factory,
        report_date=report_date,
    )
    sales_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="sales",
        customer_ids=frozenset({str(scoped_customer_id)}),
    )
    app = create_app()
    app.dependency_overrides[get_session] = _session_override(online_db.session_factory)
    app.dependency_overrides[get_system_actor] = lambda: sales_actor

    with TestClient(app) as client:
        response = client.get("/views/recharge_view/records")

    assert response.status_code == 200
    records = response.json()["records"]
    assert len(records) == 1
    fields = records[0]["fields"]
    assert fields["customer_id"] == str(scoped_customer_id)
    assert fields["customer_id"] != str(unscoped_customer_id)
    assert fields["amount"] == "[masked]"
    assert fields["currency"] == "USD"
    assert fields["collection_status"] == "confirmed"
    assert fields["execution_status"] == "succeeded"
    assert fields["readback_status"] == "failed"


def test_online_outbox_dispatcher_processes_database_backed_events(
    online_db: OnlineDatabase,
) -> None:
    with online_db.session_factory.begin() as session:
        event = OutboxEvent(
            id=uuid4(),
            event_type="stage02.online.noop",
            payload={"ok": True},
            status="pending",
            attempts=0,
            attempt_count=0,
            max_attempts=3,
            idempotency_key="stage02-online-noop",
            trace_id="outbox:online:noop",
        )
        session.add(event)
        event_id = event.id

    handled_payloads = []
    with online_db.session_factory.begin() as session:
        dispatcher = OutboxDispatcher(
            repository=SqlAlchemyOutboxRepository(session),
            handlers={
                "stage02.online.noop": lambda handled_event: handled_payloads.append(
                    handled_event.payload
                )
            },
            audit_session=session,
        )
        result = dispatcher.dispatch_once()

    assert result.processed == 1
    assert handled_payloads == [{"ok": True}]
    with online_db.session_factory() as session:
        stored_event = session.get(OutboxEvent, event_id)
        assert stored_event.status == "processed"
        assert stored_event.processed_at is not None


def test_online_outbox_dispatcher_retries_then_dead_letters_database_backed_event(
    online_db: OnlineDatabase,
) -> None:
    with online_db.session_factory.begin() as session:
        event = OutboxEvent(
            id=uuid4(),
            event_type="stage02.online.retryable",
            payload={"ok": False},
            status="pending",
            attempts=0,
            attempt_count=0,
            max_attempts=2,
            idempotency_key="stage02-online-retryable",
            trace_id="outbox:online:retryable",
        )
        session.add(event)
        event_id = event.id

    def failing_handler(_event: OutboxEvent) -> None:
        raise RetryableOutboxError("temporary_online_failure")

    with online_db.session_factory.begin() as session:
        dispatcher = OutboxDispatcher(
            repository=SqlAlchemyOutboxRepository(session),
            handlers={"stage02.online.retryable": failing_handler},
            audit_session=session,
        )
        first_result = dispatcher.dispatch_once()

    assert first_result.retried == 1
    with online_db.session_factory.begin() as session:
        stored_event = session.get(OutboxEvent, event_id)
        assert stored_event.status == "retry"
        assert stored_event.attempts == 1
        assert stored_event.attempt_count == 1
        assert stored_event.last_error == "temporary_online_failure"
        stored_event.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with online_db.session_factory.begin() as session:
        dispatcher = OutboxDispatcher(
            repository=SqlAlchemyOutboxRepository(session),
            handlers={"stage02.online.retryable": failing_handler},
            audit_session=session,
        )
        second_result = dispatcher.dispatch_once()

    assert second_result.dead_lettered == 1
    with online_db.session_factory() as session:
        stored_event = session.get(OutboxEvent, event_id)
        assert stored_event.status == "dead_letter"
        assert stored_event.attempts == 2
        assert stored_event.attempt_count == 2
        assert stored_event.last_error == "temporary_online_failure"
        audit_event = session.scalar(
            select(OpsAuditEvent).where(
                OpsAuditEvent.event_type == "outbox_dead_letter"
            )
        )
        assert audit_event is not None
        assert audit_event.entity_id == event_id
        assert audit_event.after_state["error_code"] == "retry_exhausted"


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _assert_disposable_database_url(database_url: str) -> None:
    url = make_url(database_url)
    if url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Online Stage 02 smoke tests only allow local PostgreSQL")
    database = url.database or ""
    if "stage02" not in database and "test" not in database:
        raise RuntimeError(
            "Online Stage 02 smoke tests require a disposable database name"
        )


def _reset_public_schema(engine: Engine) -> None:
    with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as connection:
        connection.execute(text("drop schema if exists public cascade"))
        connection.execute(text("create schema public"))
        connection.execute(text("grant all on schema public to public"))


def _session_override(session_factory):
    def override() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    return override


def _seed_customer_group(
    session_factory,
    *,
    customer_id,
    telegram_chat_id: str,
) -> None:
    with session_factory.begin() as session:
        session.add(
            Customer(
                id=customer_id,
                name="Stage 02 Online Customer",
                normalized_name=f"stage02-online-{customer_id}",
                status="active",
                risk_level="low",
            )
        )
        session.add(
            CustomerGroup(
                id=uuid4(),
                customer_id=customer_id,
                telegram_chat_id=telegram_chat_id,
                group_title="Stage 02 Online Group",
                group_type="customer_group",
                status="active",
            )
        )


def _seed_pending_service_draft(session_factory, *, customer_id):
    draft_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            Customer(
                id=customer_id,
                name="Stage 02 Confirmation Customer",
                normalized_name=f"stage02-confirmation-{customer_id}",
                status="active",
                risk_level="low",
            )
        )
        session.add(
            ServiceDraft(
                id=draft_id,
                draft_type="recharge",
                status="pending_confirmation",
                customer_id=customer_id,
                created_by_type="agent",
                created_by_id="mock_router",
                payload={"amount": "100.00", "currency": "USD"},
                missing_fields=[],
                risk_flags=[],
                confidence="0.9000",
                trace_id=f"draft:{draft_id}",
                idempotency_key=f"draft:{draft_id}:recharge",
            )
        )
    return draft_id


def _seed_customer(session_factory):
    customer_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            Customer(
                id=customer_id,
                name="Stage 02 Online Seed Customer",
                normalized_name=f"stage02-seed-{customer_id}",
                status="active",
                risk_level="low",
            )
        )
    return customer_id


def _seed_reporting_facts(session_factory, *, report_date: date):
    customer_id = uuid4()
    account_asset_id = uuid4()
    service_record_id = uuid4()
    ticket_id = uuid4()
    recharge_id = uuid4()
    payment_profile_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            Customer(
                id=customer_id,
                name="Stage 02 Reporting Customer",
                normalized_name=f"stage02-reporting-{customer_id}",
                status="active",
                risk_level="low",
            )
        )
        session.flush()
        session.add(
            AccountAsset(
                id=account_asset_id,
                customer_id=customer_id,
                external_account_id=f"act_reporting_{account_asset_id}",
                account_name="Reporting Account",
                platform="meta",
                status="active",
                risk_status="normal",
            )
        )
        session.flush()
        session.add(
            AccountDailyMetric(
                id=uuid4(),
                account_asset_id=account_asset_id,
                customer_id=customer_id,
                metric_date=report_date,
                balance_amount=Decimal("100.00"),
                balance_currency="USD",
                spend_amount=Decimal("41.50"),
                spend_currency="USD",
                freshness_at=datetime(2026, 7, 4, 9, 30, tzinfo=timezone.utc),
                source="online_smoke",
                read_status="fresh",
            )
        )
        session.add(
            ServiceRecord(
                id=service_record_id,
                service_type="recharge",
                status="succeeded",
                customer_id=customer_id,
                account_asset_id=account_asset_id,
                idempotency_key=f"service:{service_record_id}",
                trace_id=f"service:{service_record_id}",
            )
        )
        session.flush()
        session.add(
            ExecutionTicket(
                id=ticket_id,
                approved_by_user_id=uuid4(),
                allowed_action="execution.recharge",
                allowed_customer_id=customer_id,
                allowed_account_id=account_asset_id,
                risk_snapshot={},
                permission_snapshot={},
                idempotency_key=f"ticket:{ticket_id}",
                status="used",
                trace_id=f"ticket:{ticket_id}",
            )
        )
        session.flush()
        session.add(
            RechargeRecord(
                id=recharge_id,
                service_record_id=service_record_id,
                customer_id=customer_id,
                account_asset_id=account_asset_id,
                amount=Decimal("250.00"),
                currency="USD",
                collection_status="confirmed",
                execution_status="succeeded",
                readback_status="failed",
                readback_at=datetime(2026, 7, 4, 10, 30, tzinfo=timezone.utc),
                execution_ticket_id=ticket_id,
            )
        )
        session.add(
            PaymentProfile(
                id=payment_profile_id,
                provider="stripe",
                tokenized_profile_id=f"tok_{payment_profile_id}",
                masked_label="Visa **** 4242",
                last4="4242",
                brand="visa",
                status="active",
                customer_id=customer_id,
            )
        )
        session.flush()
        session.add(
            AccountCardBinding(
                id=uuid4(),
                account_asset_id=account_asset_id,
                payment_profile_id=payment_profile_id,
                customer_id=customer_id,
                binding_status="bound",
                one_card_one_account_policy="strict",
                bound_at=datetime(2026, 7, 4, 12, 30, tzinfo=timezone.utc),
                trace_id=f"binding:{account_asset_id}",
            )
        )
    return customer_id, account_asset_id


def _seed_stale_reporting_metric(session_factory, *, report_date: date):
    customer_id = uuid4()
    account_asset_id = uuid4()
    metric_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            Customer(
                id=customer_id,
                name="Stage 02 Stale Reporting Customer",
                normalized_name=f"stage02-stale-reporting-{customer_id}",
                status="active",
                risk_level="medium",
            )
        )
        session.flush()
        session.add(
            AccountAsset(
                id=account_asset_id,
                customer_id=customer_id,
                external_account_id=f"act_stale_reporting_{account_asset_id}",
                account_name="Stale Reporting Account",
                platform="meta",
                status="active",
                risk_status="watch",
            )
        )
        session.flush()
        session.add(
            AccountDailyMetric(
                id=metric_id,
                account_asset_id=account_asset_id,
                customer_id=customer_id,
                metric_date=report_date,
                balance_amount=Decimal("100.00"),
                balance_currency="USD",
                spend_amount=None,
                spend_currency="USD",
                freshness_at=datetime(2026, 7, 3, 23, 30, tzinfo=timezone.utc),
                source="online_smoke",
                read_status="stale_data",
            )
        )
    return customer_id, metric_id


def _seed_confirmed_recharge_service(session_factory):
    customer_id = uuid4()
    service_record_id = uuid4()
    ticket_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            Customer(
                id=customer_id,
                name="Stage 02 Recharge Customer",
                normalized_name=f"stage02-recharge-{customer_id}",
                status="active",
                risk_level="low",
            )
        )
        session.add(
            ServiceRecord(
                id=service_record_id,
                service_type="recharge",
                status="pending",
                customer_id=customer_id,
                idempotency_key=f"service:{service_record_id}",
                trace_id=f"service:{service_record_id}",
            )
        )
        session.add(
            ExecutionTicket(
                id=ticket_id,
                approved_by_user_id=uuid4(),
                allowed_action="execution.recharge",
                allowed_customer_id=customer_id,
                risk_snapshot={},
                permission_snapshot={},
                idempotency_key=f"ticket:{ticket_id}",
                status="issued",
                trace_id=f"ticket:{ticket_id}",
            )
        )
    return service_record_id, ticket_id


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0
