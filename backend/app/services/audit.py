from collections.abc import Mapping, MutableMapping
from typing import Any
from uuid import UUID

from app.models.audit import OpsAuditEvent

SENSITIVE_AUDIT_KEYS = {
    "card_number",
    "cvv",
    "raw_card_number",
    "raw_payment_credential",
}
REDACTED_VALUE = "[redacted]"


def redact_sensitive_state(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: MutableMapping[str, Any] = {}
        for key, item in value.items():
            if key in SENSITIVE_AUDIT_KEYS:
                redacted[key] = REDACTED_VALUE
            else:
                redacted[key] = redact_sensitive_state(item)
        return dict(redacted)
    if isinstance(value, list):
        return [redact_sensitive_state(item) for item in value]
    return value


def record_audit_event(
    session: Any,
    *,
    trace_id: str,
    actor_type: str,
    actor_id: str,
    event_type: str,
    entity_type: str,
    entity_id: UUID | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    permission_snapshot: dict[str, Any] | None = None,
) -> OpsAuditEvent:
    event = OpsAuditEvent(
        trace_id=trace_id,
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=redact_sensitive_state(before_state),
        after_state=redact_sensitive_state(after_state),
        permission_snapshot=redact_sensitive_state(permission_snapshot),
    )
    session.add(event)
    return event
