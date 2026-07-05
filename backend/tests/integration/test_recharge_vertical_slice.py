from decimal import Decimal
from uuid import uuid4

from app.models.service_drafts import ServiceDraft
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
    mark_readback_failed,
)
from app.workers.handlers import handle_execution_recharge


def test_confirmed_recharge_draft_runs_mock_execution_and_separate_readback_failure() -> None:
    draft = ServiceDraft(
        id=uuid4(),
        draft_type="recharge",
        status="pending_confirmation",
        customer_id=uuid4(),
        source_message_id=uuid4(),
        created_by_type="agent",
        created_by_id="mock_router",
        payload={"account_id": "act_1001", "amount": "1000", "currency": "USD"},
        missing_fields=[],
        risk_flags=[],
        confidence=Decimal("0.9000"),
        trace_id="trace-1",
        idempotency_key="draft:message-1:recharge",
    )
    actor = Actor(actor_type="user", actor_id=str(uuid4()), role="production")
    confirmation = confirm_service_draft(
        InMemoryConfirmationUnitOfWork(service_drafts=[draft]),
        draft.id,
        actor,
    )
    recharge_uow = InMemoryRechargeUnitOfWork(
        service_records=[confirmation.service_record],
        execution_tickets=[confirmation.execution_ticket],
    )

    recharge = create_recharge_record_from_confirmation(
        recharge_uow,
        service_record=confirmation.service_record,
        ticket=confirmation.execution_ticket,
        amount=Decimal("1000"),
        currency="USD",
    )
    collection = create_collection_record_for_recharge(
        recharge_uow,
        recharge=recharge,
        collection_method="bank",
    )
    confirm_collection(
        recharge_uow,
        collection.id,
        confirmed_by_user_id=uuid4(),
    )
    handle_execution_recharge({"recharge_id": str(recharge.id)}, recharge_uow)
    mark_readback_failed(
        recharge_uow,
        recharge.id,
        error_message="mock readback failed",
    )

    assert confirmation.execution_ticket.status == "used"
    assert recharge.collection_status == "confirmed"
    assert recharge.execution_status == "succeeded"
    assert recharge.readback_status == "failed"
    assert recharge_uow.execution_logs[0].execution_status == "succeeded"
    assert recharge_uow.outbox_events[0].event_type == "readback.balance"
