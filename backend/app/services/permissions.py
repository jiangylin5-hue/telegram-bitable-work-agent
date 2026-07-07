from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.services.audit import record_audit_event

MASKED_VALUE = "[masked]"
GLOBAL_RECORD_ROLES = frozenset({"admin", "manager"})
SENSITIVE_FIELDS = frozenset(
    {
        "amount",
        "balance",
        "spend",
        "payment_profile",
        "tokenized_payment_profile",
        "failure_reason",
        "raw_text",
        "execution_response_summary",
        "notes",
    }
)

FIELD_ALLOWLIST_BY_ROLE = {
    "admin": SENSITIVE_FIELDS,
    "manager": SENSITIVE_FIELDS,
    "finance": frozenset({"amount", "balance", "spend", "failure_reason"}),
    "production": frozenset({"failure_reason"}),
    "customer_service": frozenset({"raw_text", "failure_reason", "notes"}),
    "sales": frozenset(),
    "agent": frozenset({"amount", "balance", "spend"}),
}

ACTION_ALLOWLIST_BY_ROLE = {
    "admin": frozenset({"*"}),
    "manager": frozenset(
        {
            "create_draft",
            "confirm_draft",
            "reject_draft",
            "request_more_info",
            "escalate_review",
            "view_audit",
            "export_data",
        }
    ),
    "finance": frozenset(
        {"create_draft", "confirm_draft", "reject_draft", "request_more_info"}
    ),
    "production": frozenset(
        {"create_draft", "confirm_draft", "reject_draft", "request_more_info"}
    ),
    "customer_service": frozenset(
        {"create_draft", "reject_draft", "request_more_info"}
    ),
    "sales": frozenset({"create_draft"}),
    "agent": frozenset(
        {
            "create_draft",
            "escalate_review",
            "execute_after_confirmation",
            "propose_account_assignment",
        }
    ),
}

ACTION_ALLOWLIST_BY_ROLE["production"] = ACTION_ALLOWLIST_BY_ROLE["production"] | {
    "create_inventory_account",
    "confirm_account_assignment",
    "activate_inventory_account",
}
ACTION_ALLOWLIST_BY_ROLE["manager"] = ACTION_ALLOWLIST_BY_ROLE["manager"] | {
    "create_inventory_account",
    "confirm_account_assignment",
    "activate_inventory_account",
    "view_company_report",
    "manage_telegram_binding",
    "request_test_telegram_send",
    "confirm_test_telegram_send",
}
ACTION_ALLOWLIST_BY_ROLE["admin"] = frozenset({"*"})


class PermissionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class Actor:
    actor_type: str
    actor_id: str
    role: str
    customer_ids: frozenset[str] = frozenset()


def can_view_customer_record(actor: Actor, customer_id: str | UUID | None) -> bool:
    if actor.role in GLOBAL_RECORD_ROLES:
        return True
    if customer_id is None:
        return False
    return str(customer_id) in actor.customer_ids


def allowed_fields_for_actor(actor: Actor, fields: set[str]) -> set[str]:
    role_sensitive_allowlist = FIELD_ALLOWLIST_BY_ROLE.get(actor.role, frozenset())
    return {
        field
        for field in fields
        if field not in SENSITIVE_FIELDS or field in role_sensitive_allowlist
    }


def filter_record_fields(actor: Actor, fields: dict[str, Any]) -> dict[str, Any]:
    allowed_fields = allowed_fields_for_actor(actor, set(fields))
    return {
        key: value if key in allowed_fields else MASKED_VALUE
        for key, value in fields.items()
    }


def can_perform_action(actor: Actor, action: str) -> bool:
    allowed_actions = ACTION_ALLOWLIST_BY_ROLE.get(actor.role, frozenset())
    return "*" in allowed_actions or action in allowed_actions


def assert_action_allowed(
    actor: Actor,
    action: str,
    *,
    session: Any,
    trace_id: str,
    entity_type: str,
    entity_id: UUID | None = None,
) -> None:
    if can_perform_action(actor, action):
        return

    record_audit_event(
        session,
        trace_id=trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="permission_denied",
        entity_type=entity_type,
        entity_id=entity_id,
        permission_snapshot={
            "action": action,
            "role": actor.role,
            "actor_type": actor.actor_type,
        },
    )
    raise PermissionDenied(f"{actor.role} cannot perform {action}")


def can_auto_mark_account_exception(actor: Actor) -> bool:
    return (
        actor.role in {"admin", "manager"}
        or (
            actor.actor_type == "agent"
            and actor.actor_id == "account_inventory_agent"
        )
    )


def assert_auto_mark_account_exception_allowed(
    actor: Actor,
    *,
    session: Any,
    trace_id: str,
    entity_type: str,
    entity_id: UUID | None = None,
) -> None:
    if can_auto_mark_account_exception(actor):
        return

    record_audit_event(
        session,
        trace_id=trace_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="permission_denied",
        entity_type=entity_type,
        entity_id=entity_id,
        permission_snapshot={
            "action": "auto_mark_account_exception",
            "role": actor.role,
            "actor_type": actor.actor_type,
            "actor_id": actor.actor_id,
        },
    )
    raise PermissionDenied(
        f"{actor.role}:{actor.actor_id} cannot perform auto_mark_account_exception"
    )
