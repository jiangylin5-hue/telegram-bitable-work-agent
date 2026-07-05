from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.agents.mock_reporting import MockReportingAgent
from app.api.routes.mock_telegram import get_telegram_ingestion_uow
from app.main import create_app
from app.models.reporting import AccountDailyMetric
from app.services.account_inventory import (
    InMemoryAccountInventoryUnitOfWork,
    confirm_account_assignment,
    create_inventory_account,
    propose_account_assignment,
)
from app.services.confirmation import (
    InMemoryConfirmationUnitOfWork,
    confirm_service_draft,
)
from app.services.permissions import Actor
from app.services.recharge import (
    InMemoryRechargeUnitOfWork,
    confirm_collection,
    create_collection_record_for_recharge,
    create_recharge_record_from_confirmation,
)
from app.services.reporting import (
    InMemoryReportingUnitOfWork,
    generate_company_daily_report,
    get_company_report_for_actor,
)
from app.services.service_drafts import InMemoryServiceDraftUnitOfWork
from app.services.telegram_ingestion import InMemoryTelegramIngestionUnitOfWork
from app.services.bitable_views import get_view_definition
from app.workers.handlers import (
    handle_agent_intent_extract,
    handle_execution_recharge,
    handle_readback_balance,
)


def test_stage_02_e2e_critical_path_without_real_external_writes() -> None:
    customer_id = uuid4()
    production_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="production",
    )
    manager_actor = Actor(
        actor_type="user",
        actor_id=str(uuid4()),
        role="manager",
    )
    agent_actor = Actor(
        actor_type="agent",
        actor_id="stage-02-e2e-agent",
        role="agent",
        customer_ids=frozenset({str(customer_id)}),
    )

    draft = _ingest_recharge_message_and_route_to_draft(customer_id)
    confirmation = confirm_service_draft(
        InMemoryConfirmationUnitOfWork(service_drafts=[draft]),
        draft.id,
        production_actor,
    )

    recharge_uow = InMemoryRechargeUnitOfWork(
        service_records=[confirmation.service_record],
        execution_tickets=[confirmation.execution_ticket],
    )
    recharge = create_recharge_record_from_confirmation(
        recharge_uow,
        service_record=confirmation.service_record,
        ticket=confirmation.execution_ticket,
        amount=Decimal(draft.payload["amount"]),
        currency=draft.payload["currency"],
    )
    collection = create_collection_record_for_recharge(
        recharge_uow,
        recharge=recharge,
        collection_method="bank",
    )
    confirm_collection(
        recharge_uow,
        collection.id,
        confirmed_by_user_id=UUID(production_actor.actor_id),
    )
    handle_execution_recharge({"recharge_id": str(recharge.id)}, recharge_uow)
    handle_readback_balance(
        {"recharge_id": str(recharge.id), "simulate": "failed"},
        recharge_uow,
    )

    inventory_uow = InMemoryAccountInventoryUnitOfWork()
    inventory_account = create_inventory_account(
        inventory_uow,
        actor=production_actor,
        platform="meta",
        external_account_id=draft.payload["account_id"],
        production_batch_id="stage-02-e2e",
    )
    assignment = propose_account_assignment(
        inventory_uow,
        actor=agent_actor,
        account_inventory_id=inventory_account.id,
        customer_id=customer_id,
    )
    confirm_account_assignment(
        inventory_uow,
        actor=production_actor,
        assignment_id=assignment.id,
    )

    report_date = date(2026, 7, 4)
    reporting_uow = InMemoryReportingUnitOfWork(
        metrics=[
            AccountDailyMetric(
                id=uuid4(),
                account_asset_id=uuid4(),
                customer_id=customer_id,
                metric_date=report_date,
                balance_amount=Decimal("500.00"),
                balance_currency="USD",
                spend_amount=Decimal("1000.00"),
                spend_currency="USD",
                freshness_at=datetime(2026, 7, 4, 9, 30, tzinfo=timezone.utc),
                source="mock_readback",
                read_status="fresh",
            )
        ],
    )
    customer_report = MockReportingAgent().generate_customer_report(
        reporting_uow,
        actor=agent_actor,
        customer_id=customer_id,
        report_date=report_date,
    )
    company_report = generate_company_daily_report(
        reporting_uow,
        actor=manager_actor,
        report_date=report_date,
    )

    assert draft.status == "confirmed"
    assert confirmation.execution_ticket.status == "used"
    assert recharge.collection_status == "confirmed"
    assert recharge.execution_status == "succeeded"
    assert recharge.readback_status == "failed"
    assert recharge_uow.execution_logs[0].execution_status == "succeeded"
    assert inventory_account.inventory_status == "allocated"
    assert inventory_account.assigned_customer_id == customer_id
    assert customer_report.report_payload["metrics"][0]["source"] == "mock_readback"
    assert customer_report.report_payload["metrics"][0]["freshness_at"]
    assert company_report.report_payload["total_spend_by_currency"]["USD"] == "1000.00"
    assert get_company_report_for_actor(
        reporting_uow,
        actor=manager_actor,
        report=company_report,
    ) == company_report
    assert get_view_definition("customer_daily_reports").table_name == (
        "customer_daily_reports"
    )
    assert get_view_definition("company_daily_reports").table_name == (
        "company_daily_reports"
    )


def _ingest_recharge_message_and_route_to_draft(customer_id):
    app = create_app()
    ingestion_uow = InMemoryTelegramIngestionUnitOfWork()
    ingestion_uow.bind_customer_group(
        telegram_chat_id="chat-stage-02",
        customer_group_id=uuid4(),
        customer_id=customer_id,
    )
    app.dependency_overrides[get_telegram_ingestion_uow] = lambda: ingestion_uow

    with TestClient(app) as client:
        response = client.post(
            "/mock/telegram/updates",
            json={
                "update_id": "stage-02-e2e-update",
                "chat_id": "chat-stage-02",
                "message_id": "stage-02-e2e-message",
                "sender_user_id": "customer-user",
                "username": "customer_user",
                "text": "recharge act_1001 1000 USD",
            },
        )

    draft_uow = InMemoryServiceDraftUnitOfWork(messages=ingestion_uow.messages)
    handle_agent_intent_extract(ingestion_uow.outbox_events[0], draft_uow)

    assert response.status_code == 200
    assert response.json()["status"] == "stored"
    assert ingestion_uow.outbox_events[0].event_type == "agent.intent_extract"
    assert draft_uow.service_drafts[0].status == "pending_confirmation"
    return draft_uow.service_drafts[0]
