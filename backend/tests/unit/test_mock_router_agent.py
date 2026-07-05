from uuid import uuid4

from app.models.outbox import OutboxEvent
from app.agents.mock_router import route_message_to_draft_candidate
from app.services.service_drafts import InMemoryServiceDraftUnitOfWork
from app.services.telegram_ingestion import IngestedMessage
from app.workers.handlers import handle_agent_intent_extract


def test_recharge_phrase_creates_pending_confirmation_draft() -> None:
    message_id = uuid4()
    message = IngestedMessage(
        id=message_id,
        telegram_update_id="update-1",
        telegram_chat_id="chat-1",
        telegram_message_id="message-1",
        customer_group_id=uuid4(),
        customer_id=uuid4(),
        raw_text="给账户 act_1001 充值 1000 USD",
        raw_caption=None,
        normalized_text="给账户 act_1001 充值 1000 USD",
        message_type="text",
        intent_status="unclassified",
        intent_type=None,
        ingestion_status="stored",
        trace_id="trace-1",
    )
    uow = InMemoryServiceDraftUnitOfWork(messages=[message])
    event = OutboxEvent(
        event_type="agent.intent_extract",
        payload={"message_id": str(message_id)},
        status="pending",
        attempts=0,
        max_attempts=3,
        idempotency_key=f"intent:{message_id}",
        trace_id="trace-1",
    )

    handle_agent_intent_extract(event, uow)

    assert message.intent_status == "routed"
    assert message.intent_type == "recharge"
    assert len(uow.service_drafts) == 1
    draft = uow.service_drafts[0]
    assert draft.draft_type == "recharge"
    assert draft.status == "pending_confirmation"
    assert draft.payload == {
        "account_id": "act_1001",
        "amount": "1000",
        "currency": "USD",
    }
    assert len(uow.audit_events) == 1
    assert uow.audit_events[0].event_type == "draft_created"


def test_inventory_request_is_structured_as_account_inventory_draft() -> None:
    message = make_message("need unused account for customer Alpha")

    candidate = route_message_to_draft_candidate(message)

    assert candidate.intent_type == "account_inventory_request"
    assert candidate.draft_type == "account_inventory_request"
    assert candidate.status == "pending_confirmation"
    assert candidate.payload["request_type"] == "unused_account"
    assert candidate.missing_fields == []
    assert candidate.account_hint is None


def test_report_request_is_structured_as_customer_daily_report_draft() -> None:
    message = make_message("send customer daily report for Alpha")

    candidate = route_message_to_draft_candidate(message)

    assert candidate.intent_type == "report_request"
    assert candidate.draft_type == "customer_daily_report"
    assert candidate.status == "pending_confirmation"
    assert candidate.payload["report_type"] == "customer_daily"
    assert candidate.missing_fields == []


def test_ambiguous_phrase_enters_needs_review() -> None:
    message = make_message("please handle this when possible")

    candidate = route_message_to_draft_candidate(message)

    assert candidate.intent_type == "unknown"
    assert candidate.status == "needs_review"
    assert candidate.missing_fields == ["intent_type"]


def make_message(text: str) -> IngestedMessage:
    return IngestedMessage(
        id=uuid4(),
        telegram_update_id="update-router",
        telegram_chat_id="chat-router",
        telegram_message_id="message-router",
        customer_group_id=uuid4(),
        customer_id=uuid4(),
        raw_text=text,
        raw_caption=None,
        normalized_text=text,
        message_type="text",
        intent_status="unclassified",
        intent_type=None,
        ingestion_status="stored",
        trace_id="trace-router",
    )
