from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes.confirmations import get_confirmation_uow
from app.main import create_app
from app.models.service_drafts import ServiceDraft
from app.models.telegram import Message, TelegramSendRequest
from app.services.confirmation import (
    ConfirmationStateError,
    InMemoryConfirmationUnitOfWork,
    confirm_service_draft,
)
from app.services.permissions import Actor, PermissionDenied


def test_customer_reply_confirmation_creates_send_request_without_ticket_or_outbox() -> None:
    message = _message(telegram_chat_id="stage05-test-chat")
    draft = _stage05_draft(
        draft_type="customer_reply",
        created_by_id="customer_reply_draft_agent",
        source_message_id=message.id,
        payload={"reply_text": "We are checking the account and will update you."},
    )
    uow = InMemoryConfirmationUnitOfWork(
        service_drafts=[draft],
        messages=[message],
    )
    actor = _manager()

    result = confirm_service_draft(
        uow,
        draft.id,
        actor,
        allowed_chat_ids=("stage05-test-chat",),
    )

    assert draft.status == "confirmed"
    assert result.side_effect == "customer_reply_send_request_created"
    assert result.service_record is None
    assert result.execution_ticket is None
    assert result.execution_log is None
    assert result.telegram_send_request is not None
    assert result.telegram_send_request.target_chat_id == "stage05-test-chat"
    assert result.telegram_send_request.message_text == (
        "We are checking the account and will update you."
    )
    assert result.telegram_send_request.status == "pending_confirmation"
    assert result.telegram_send_request.trace_id == f"reply-send:{draft.id}"
    assert uow.service_records == []
    assert uow.execution_tickets == []
    assert uow.execution_logs == []
    assert uow.outbox_events == []
    assert [event.event_type for event in uow.audit_events] == [
        "customer_reply_send_requested",
        "draft_confirmed",
    ]


def test_customer_reply_confirmation_blocks_non_allowlisted_target_without_outbox() -> None:
    message = _message(telegram_chat_id="real-customer-chat")
    draft = _stage05_draft(
        draft_type="customer_reply",
        created_by_id="customer_reply_draft_agent",
        source_message_id=message.id,
        payload={"reply_text": "We are checking it now."},
    )
    uow = InMemoryConfirmationUnitOfWork(
        service_drafts=[draft],
        messages=[message],
    )

    result = confirm_service_draft(
        uow,
        draft.id,
        _manager(),
        allowed_chat_ids=("stage05-test-chat",),
    )

    assert draft.status == "confirmed"
    assert result.telegram_send_request is not None
    assert result.telegram_send_request.status == "blocked"
    assert result.telegram_send_request.last_error_code == (
        "telegram_test_send_target_not_allowlisted"
    )
    assert uow.outbox_events == []
    assert uow.audit_events[0].event_type == "customer_reply_send_requested"
    assert uow.audit_events[0].after_state["status"] == "blocked"


def test_customer_reply_confirmation_reuses_existing_send_request_by_trace() -> None:
    message = _message(telegram_chat_id="stage05-test-chat")
    draft = _stage05_draft(
        draft_type="customer_reply",
        created_by_id="customer_reply_draft_agent",
        source_message_id=message.id,
        payload={"reply_text": "We are checking it now."},
    )
    existing_request = _send_request(
        trace_id=f"reply-send:{draft.id}",
        target_chat_id="stage05-test-chat",
        message_text="We are checking it now.",
    )
    uow = InMemoryConfirmationUnitOfWork(
        service_drafts=[draft],
        messages=[message],
        send_requests=[existing_request],
    )

    result = confirm_service_draft(
        uow,
        draft.id,
        _manager(),
        allowed_chat_ids=("stage05-test-chat",),
    )

    assert result.telegram_send_request is existing_request
    assert len(uow.send_requests) == 1
    assert draft.status == "confirmed"


@pytest.mark.parametrize(
    "draft_type,created_by_id",
    [
        ("recharge", "recharge_draft_agent"),
        ("card_binding", "card_binding_draft_agent"),
        ("bm_invite", "bm_invite_draft_agent"),
        ("account_assignment", "account_inventory_agent"),
    ],
)
def test_stage05_business_confirmation_creates_noop_evidence_without_ticket(
    draft_type: str,
    created_by_id: str,
) -> None:
    draft = _stage05_draft(draft_type=draft_type, created_by_id=created_by_id)
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])

    result = confirm_service_draft(
        uow,
        draft.id,
        _manager(),
        allowed_chat_ids=("stage05-test-chat",),
    )

    assert draft.status == "service_record_created"
    assert result.side_effect == "noop_service_evidence_created"
    assert result.service_record is not None
    assert result.service_record.service_type == draft_type
    assert result.service_record.status == "recorded"
    assert result.execution_ticket is None
    assert result.telegram_send_request is None
    assert result.execution_log is not None
    assert result.execution_log.provider == "noop"
    assert result.execution_log.execution_status == "skipped"
    assert result.execution_log.provider_request_id == (
        f"noop-execution:{result.service_record.id}"
    )
    assert result.execution_log.request_summary == {
        "draft_id": str(draft.id),
        "draft_type": draft_type,
        "provider_execution_allowed": False,
    }
    assert uow.execution_tickets == []
    assert [event.event_type for event in uow.audit_events] == [
        "business_noop_evidence_created",
        "draft_confirmed",
    ]


@pytest.mark.parametrize(
    "status",
    [
        "needs_more_info",
        "manual_review",
        "rejected",
        "confirmed",
        "service_record_created",
    ],
)
def test_stage05_confirmation_wrong_states_return_stable_conflict_without_side_effects(
    status: str,
) -> None:
    draft = _stage05_draft(
        draft_type="recharge",
        created_by_id="recharge_draft_agent",
        status=status,
    )
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])

    with pytest.raises(ConfirmationStateError, match=f"Draft cannot be confirmed from {status}"):
        confirm_service_draft(
            uow,
            draft.id,
            _manager(),
            allowed_chat_ids=("stage05-test-chat",),
        )

    assert uow.service_records == []
    assert uow.execution_tickets == []
    assert uow.execution_logs == []
    assert uow.send_requests == []
    assert uow.audit_events == []


def test_stage05_business_confirmation_repeated_call_does_not_duplicate_side_effects() -> None:
    draft = _stage05_draft(draft_type="recharge", created_by_id="recharge_draft_agent")
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])

    confirm_service_draft(
        uow,
        draft.id,
        _manager(),
        allowed_chat_ids=("stage05-test-chat",),
    )

    with pytest.raises(
        ConfirmationStateError,
        match="Draft cannot be confirmed from service_record_created",
    ):
        confirm_service_draft(
            uow,
            draft.id,
            _manager(),
            allowed_chat_ids=("stage05-test-chat",),
        )

    assert len(uow.service_records) == 1
    assert len(uow.execution_logs) == 1
    assert len(uow.execution_tickets) == 0
    assert len(uow.audit_events) == 2


def test_agent_cannot_confirm_stage05_draft_and_denial_is_audited() -> None:
    draft = _stage05_draft(draft_type="recharge", created_by_id="recharge_draft_agent")
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])

    with pytest.raises(PermissionDenied):
        confirm_service_draft(
            uow,
            draft.id,
            Actor(actor_type="agent", actor_id="recharge_draft_agent", role="agent"),
            allowed_chat_ids=("stage05-test-chat",),
        )

    assert draft.status == "pending_confirmation"
    assert uow.service_records == []
    assert uow.execution_tickets == []
    assert uow.execution_logs == []
    assert uow.audit_events[0].event_type == "permission_denied"


def test_production_role_cannot_confirm_stage05_business_draft() -> None:
    draft = _stage05_draft(draft_type="recharge", created_by_id="recharge_draft_agent")
    uow = InMemoryConfirmationUnitOfWork(service_drafts=[draft])

    with pytest.raises(PermissionDenied):
        confirm_service_draft(
            uow,
            draft.id,
            Actor(actor_type="user", actor_id=str(uuid4()), role="production"),
            allowed_chat_ids=("stage05-test-chat",),
        )

    assert draft.status == "pending_confirmation"
    assert uow.service_records == []
    assert uow.execution_logs == []
    assert uow.audit_events[0].event_type == "permission_denied"
    assert uow.audit_events[0].permission_snapshot["role"] == "production"


def test_confirmation_api_returns_stage05_customer_reply_side_effect_fields() -> None:
    app = create_app()
    message = _message(telegram_chat_id="stage05-test-chat")
    draft = _stage05_draft(
        draft_type="customer_reply",
        created_by_id="customer_reply_draft_agent",
        source_message_id=message.id,
        payload={"reply_text": "We are checking it now."},
    )
    uow = InMemoryConfirmationUnitOfWork(
        service_drafts=[draft],
        messages=[message],
        allowed_chat_ids=("stage05-test-chat",),
    )
    app.dependency_overrides[get_confirmation_uow] = lambda: uow

    with TestClient(app) as client:
        response = client.post(
            f"/confirmations/service-drafts/{draft.id}/actions",
            json={
                "action": "confirm",
                "actor_type": "user",
                "actor_id": str(uuid4()),
                "role": "manager",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "draft_id": str(draft.id),
        "draft_status": "confirmed",
        "service_record_id": None,
        "execution_ticket_id": None,
        "telegram_send_request_id": str(uow.send_requests[0].id),
        "side_effect": "customer_reply_send_request_created",
    }
    assert uow.committed is True


def _stage05_draft(
    *,
    draft_type: str,
    created_by_id: str,
    status: str = "pending_confirmation",
    source_message_id=None,
    payload: dict[str, object] | None = None,
) -> ServiceDraft:
    return ServiceDraft(
        id=uuid4(),
        draft_type=draft_type,
        status=status,
        customer_id=uuid4(),
        source_message_id=source_message_id or uuid4(),
        source_agent_run_id=uuid4(),
        created_by_type="agent",
        created_by_id=created_by_id,
        payload=payload or {"amount": "1000", "currency": "USD", "account_id": "act_1"},
        payload_summary={},
        missing_fields=[],
        risk_flags=[],
        confidence=Decimal("0.9200"),
        intent_index=0,
        trace_id=f"trace-stage05-{draft_type}",
        idempotency_key=f"draft:{uuid4()}:{draft_type}:0",
    )


def _message(*, telegram_chat_id: str) -> Message:
    now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
    return Message(
        id=uuid4(),
        telegram_update_id=f"update-{uuid4()}",
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=f"message-{uuid4()}",
        telegram_user_id="telegram-user-1",
        customer_id=uuid4(),
        raw_text="please reply to the customer",
        normalized_text="please reply to the customer",
        message_type="text",
        intent_status="routed",
        binding_status="bound",
        processing_status="agent_succeeded",
        outbox_status="processed",
        received_at=now,
        trace_id=f"trace-message-{telegram_chat_id}",
    )


def _send_request(
    *,
    trace_id: str,
    target_chat_id: str,
    message_text: str,
) -> TelegramSendRequest:
    now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
    return TelegramSendRequest(
        id=uuid4(),
        target_chat_id=target_chat_id,
        message_text=message_text,
        status="pending_confirmation",
        requested_by_actor_type="user",
        requested_by_actor_id="manager-1",
        trace_id=trace_id,
        created_at=now,
        updated_at=now,
    )


def _manager() -> Actor:
    return Actor(actor_type="user", actor_id=str(uuid4()), role="manager")
