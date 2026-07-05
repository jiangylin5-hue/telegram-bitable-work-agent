from decimal import Decimal
from uuid import uuid4

from app.models.recharge import CollectionRecord, RechargeRecord
from app.models.service import ExecutionTicket, ServiceRecord
from app.services.recharge import (
    InMemoryRechargeUnitOfWork,
    confirm_collection,
    create_collection_record_for_recharge,
    create_recharge_record_from_confirmation,
    execute_recharge_with_mock_provider,
    mark_readback_failed,
)
from app.workers.handlers import handle_execution_recharge, handle_readback_balance


def make_recharge_record() -> RechargeRecord:
    return RechargeRecord(
        id=uuid4(),
        service_record_id=uuid4(),
        customer_id=uuid4(),
        account_asset_id=None,
        amount=Decimal("1000"),
        currency="USD",
        collection_status="pending",
        execution_status="not_started",
        readback_status="not_started",
        execution_ticket_id=None,
    )


def test_finance_confirmation_is_not_recharge_success() -> None:
    recharge = make_recharge_record()
    collection = CollectionRecord(
        id=uuid4(),
        customer_id=recharge.customer_id,
        recharge_record_id=recharge.id,
        amount=recharge.amount,
        currency=recharge.currency,
        collection_method="bank",
        collection_status="pending",
        trace_id="trace-1",
    )
    uow = InMemoryRechargeUnitOfWork(
        recharge_records=[recharge],
        collection_records=[collection],
    )

    confirm_collection(uow, collection.id, confirmed_by_user_id=uuid4())

    assert collection.collection_status == "confirmed"
    assert recharge.collection_status == "confirmed"
    assert recharge.execution_status == "not_started"
    assert uow.audit_events[0].event_type == "collection_confirmed"
    assert uow.audit_events[0].after_state["collection_status"] == "confirmed"
    assert uow.audit_events[0].after_state["recharge_execution_status"] == "not_started"


def test_mock_execution_writes_log_and_enqueues_readback() -> None:
    service_record = ServiceRecord(
        id=uuid4(),
        service_type="recharge",
        status="pending",
        customer_id=uuid4(),
        idempotency_key="service:1",
        trace_id="trace-1",
    )
    ticket = ExecutionTicket(
        id=uuid4(),
        approved_by_user_id=uuid4(),
        allowed_action="execution.recharge",
        allowed_customer_id=service_record.customer_id,
        risk_snapshot={},
        permission_snapshot={},
        idempotency_key="ticket:1",
        status="issued",
        trace_id="trace-1",
    )
    recharge = RechargeRecord(
        id=uuid4(),
        service_record_id=service_record.id,
        customer_id=service_record.customer_id,
        amount=Decimal("1000"),
        currency="USD",
        collection_status="confirmed",
        execution_status="queued",
        readback_status="not_started",
        execution_ticket_id=ticket.id,
    )
    uow = InMemoryRechargeUnitOfWork(
        service_records=[service_record],
        execution_tickets=[ticket],
        recharge_records=[recharge],
    )

    execute_recharge_with_mock_provider(uow, recharge.id)

    assert ticket.status == "used"
    assert service_record.status == "succeeded"
    assert recharge.execution_status == "succeeded"
    assert len(uow.execution_logs) == 1
    assert uow.execution_logs[0].execution_status == "succeeded"
    assert uow.outbox_events[0].event_type == "readback.balance"
    assert uow.audit_events[0].event_type == "recharge_execution_succeeded"
    assert uow.audit_events[0].after_state["execution_status"] == "succeeded"
    assert uow.audit_events[0].after_state["readback_status"] == "pending"


def test_readback_failure_remains_separate_from_execution_success() -> None:
    recharge = make_recharge_record()
    recharge.execution_status = "succeeded"
    recharge.readback_status = "pending"
    uow = InMemoryRechargeUnitOfWork(recharge_records=[recharge])

    mark_readback_failed(uow, recharge.id, error_message="mock readback failed")

    assert recharge.execution_status == "succeeded"
    assert recharge.readback_status == "failed"
    assert uow.audit_events[0].event_type == "readback_failed"


def test_execution_and_readback_handlers_call_recharge_services() -> None:
    service_record = ServiceRecord(
        id=uuid4(),
        service_type="recharge",
        status="pending",
        customer_id=uuid4(),
        idempotency_key="service:1",
        trace_id="trace-1",
    )
    ticket = ExecutionTicket(
        id=uuid4(),
        approved_by_user_id=uuid4(),
        allowed_action="execution.recharge",
        allowed_customer_id=service_record.customer_id,
        risk_snapshot={},
        permission_snapshot={},
        idempotency_key="ticket:1",
        status="issued",
        trace_id="trace-1",
    )
    recharge = RechargeRecord(
        id=uuid4(),
        service_record_id=service_record.id,
        customer_id=service_record.customer_id,
        amount=Decimal("1000"),
        currency="USD",
        collection_status="confirmed",
        execution_status="queued",
        readback_status="not_started",
        execution_ticket_id=ticket.id,
    )
    uow = InMemoryRechargeUnitOfWork(
        service_records=[service_record],
        execution_tickets=[ticket],
        recharge_records=[recharge],
    )

    handle_execution_recharge({"recharge_id": str(recharge.id)}, uow)
    handle_readback_balance(
        {"recharge_id": str(recharge.id), "simulate": "failed"},
        uow,
    )

    assert recharge.execution_status == "succeeded"
    assert recharge.readback_status == "failed"


def test_create_recharge_and_collection_records_from_confirmed_service() -> None:
    service_record = ServiceRecord(
        id=uuid4(),
        service_type="recharge",
        status="pending",
        customer_id=uuid4(),
        idempotency_key="service:1",
        trace_id="trace-1",
    )
    ticket = ExecutionTicket(
        id=uuid4(),
        approved_by_user_id=uuid4(),
        allowed_action="execution.recharge",
        allowed_customer_id=service_record.customer_id,
        risk_snapshot={},
        permission_snapshot={},
        idempotency_key="ticket:1",
        status="issued",
        trace_id="trace-1",
    )
    uow = InMemoryRechargeUnitOfWork(
        service_records=[service_record],
        execution_tickets=[ticket],
    )

    recharge = create_recharge_record_from_confirmation(
        uow,
        service_record=service_record,
        ticket=ticket,
        amount=Decimal("1000"),
        currency="USD",
    )
    collection = create_collection_record_for_recharge(
        uow,
        recharge=recharge,
        collection_method="bank",
    )

    assert recharge.execution_status == "queued"
    assert recharge.collection_status == "pending"
    assert collection.collection_status == "pending"
    assert uow.recharge_records == [recharge]
    assert uow.collection_records == [collection]
    assert [event.event_type for event in uow.audit_events] == [
        "recharge_record_created",
        "collection_record_created",
    ]
