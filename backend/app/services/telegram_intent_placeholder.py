from typing import Protocol

from app.models.telegram import Message
from app.services.audit import record_audit_event
from app.services.telegram_ingestion import IngestedMessage


class IntentPlaceholderAuditTarget(Protocol):
    def add(self, value: object) -> None:
        ...


def apply_telegram_intent_placeholder(
    message: IngestedMessage | Message,
    audit_target: IntentPlaceholderAuditTarget,
    *,
    trace_id: str,
) -> bool:
    if message.binding_status != "bound":
        return False
    if message.intent_status != "unclassified":
        return False

    before_status = message.intent_status
    message.intent_status = "intent_ready"
    message.intent_type = None
    record_audit_event(
        audit_target,
        trace_id=trace_id,
        actor_type="worker",
        actor_id="stage04_intent_placeholder",
        event_type="telegram.intent_placeholder.ready",
        entity_type="message",
        entity_id=message.id,
        before_state={
            "intent_status": before_status,
            "binding_status": message.binding_status,
        },
        after_state={
            "message_id": str(message.id),
            "intent_status": message.intent_status,
            "intent_type": message.intent_type,
            "binding_status": message.binding_status,
            "customer_id": _string_or_none(message.customer_id),
        },
    )
    return True


def _string_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)
