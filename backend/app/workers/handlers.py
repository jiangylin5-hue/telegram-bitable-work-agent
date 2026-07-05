from collections.abc import Callable

from app.agents.mock_router import route_message_to_draft_candidate
from app.models.outbox import OutboxEvent
from app.services.recharge import (
    RechargeUnitOfWork,
    execute_recharge_with_mock_provider,
    mark_readback_failed,
)
from app.services.service_drafts import (
    ServiceDraftUnitOfWork,
    create_service_draft_from_candidate,
)

OutboxHandler = Callable[[OutboxEvent], None]


def noop_handler(_event: OutboxEvent) -> None:
    return None


def handle_agent_intent_extract(
    event: OutboxEvent,
    uow: ServiceDraftUnitOfWork,
) -> None:
    message_id = event.payload["message_id"]
    message = uow.get_message(message_id)
    if message is None:
        raise ValueError(f"Message not found: {message_id}")

    candidate = route_message_to_draft_candidate(message)
    draft = create_service_draft_from_candidate(message, candidate)
    uow.mark_message_routed(message, candidate.intent_type)
    uow.add_service_draft(draft)
    uow.record_draft_created(draft, message.trace_id)


def handle_execution_recharge(
    payload: dict[str, str],
    uow: RechargeUnitOfWork,
) -> None:
    execute_recharge_with_mock_provider(uow, uuid_from_payload(payload["recharge_id"]))


def handle_readback_balance(
    payload: dict[str, str],
    uow: RechargeUnitOfWork,
) -> None:
    if payload.get("simulate") == "failed":
        mark_readback_failed(
            uow,
            uuid_from_payload(payload["recharge_id"]),
            error_message="mock readback failed",
        )


def uuid_from_payload(value: str):
    from uuid import UUID

    return UUID(value)
