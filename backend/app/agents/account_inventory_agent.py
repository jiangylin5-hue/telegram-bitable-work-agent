from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.agents.schemas import (
    AccountStatusAction,
    DraftAgentContext,
    RouterIntent,
    Stage05DraftCandidate,
)

AGENT_NAME = "account_inventory_agent"
HIGH_CONFIDENCE_THRESHOLD = Decimal("0.9000")
ALLOWED_EXCEPTION_STATUSES = frozenset({"blocked", "disabled", "risk_controlled"})
ALLOWED_EXCEPTION_RISK_FLAGS = frozenset(
    {
        "account_blocked_reported",
        "account_disabled_reported",
        "risk_control_confirmed",
    }
)
RISK_FLAG_TO_STATUS = {
    "account_blocked_reported": "blocked",
    "account_disabled_reported": "disabled",
    "risk_control_confirmed": "risk_controlled",
}


@dataclass(frozen=True)
class AccountInventoryDecision:
    status_action: AccountStatusAction | None = None
    manual_review_reasons: list[str] = field(default_factory=list)


def build_account_assignment_draft(
    intent: RouterIntent,
    context: DraftAgentContext,
) -> Stage05DraftCandidate:
    candidate_ids = _string_list_entity(intent, "candidate_account_inventory_ids")
    missing_fields = list(intent.missing_context)
    if not candidate_ids and "candidate_account_inventory_ids" not in missing_fields:
        missing_fields.append("candidate_account_inventory_ids")
    status = "pending_confirmation" if not missing_fields else "needs_more_info"
    intent_index = intent.intent_index or 0
    payload: dict[str, object] = {
        "request_type": str(intent.entities.get("request_type", "account_assignment")),
        "customer_id": context.customer_id,
        "requires_human_confirmation": True,
        "provider_execution_allowed": False,
        "replacement_action": "none",
    }
    if candidate_ids:
        payload["candidate_account_inventory_ids"] = candidate_ids
    if missing_fields:
        payload["suggested_follow_up_text"] = _follow_up_text(missing_fields)

    return Stage05DraftCandidate(
        draft_type="account_assignment",
        status=status,
        intent_type=intent.intent_type,
        intent_index=intent_index,
        payload=payload,
        payload_summary={
            "candidate_account_count": len(candidate_ids),
            "request_type": payload["request_type"],
        },
        missing_fields=missing_fields,
        risk_flags=list(intent.risk_flags),
        confidence=intent.confidence,
        source_message_id=context.source_message_id,
        source_agent_run_id=context.source_agent_run_id,
        customer_id=context.customer_id,
        created_by_type="agent",
        created_by_id=AGENT_NAME,
        agent_name=AGENT_NAME,
        trace_id=context.trace_id,
        idempotency_key=(
            f"draft:{context.source_message_id}:account_assignment:{intent_index}"
        ),
    )


def plan_account_status_exception(intent: RouterIntent) -> AccountInventoryDecision:
    target_status = _target_status(intent)
    account_hint = _account_hint(intent)
    reasons: list[str] = []
    if account_hint is None:
        reasons.append("missing_account_hint")
    if target_status not in ALLOWED_EXCEPTION_STATUSES:
        reasons.append("unsupported_status")
    if intent.confidence < HIGH_CONFIDENCE_THRESHOLD:
        reasons.append("low_confidence")
    if not (set(intent.risk_flags) & ALLOWED_EXCEPTION_RISK_FLAGS):
        reasons.append("missing_allowed_risk_flag")

    if reasons:
        return AccountInventoryDecision(manual_review_reasons=reasons)

    return AccountInventoryDecision(
        status_action=AccountStatusAction(
            account_hint=account_hint or "",
            target_status=target_status or "",
            reason=str(
                intent.entities.get(
                    "reason",
                    f"high confidence account exception: {target_status}",
                )
            ),
            confidence=intent.confidence,
            risk_flags=list(intent.risk_flags),
        )
    )


def _target_status(intent: RouterIntent) -> str | None:
    value = intent.entities.get("target_status")
    if value is not None and str(value).strip():
        return str(value).strip()
    for risk_flag in intent.risk_flags:
        if risk_flag in RISK_FLAG_TO_STATUS:
            return RISK_FLAG_TO_STATUS[risk_flag]
    return None


def _account_hint(intent: RouterIntent) -> str | None:
    for key in ("account_inventory_id", "account_id", "account_hint", "external_account_id"):
        value = intent.entities.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _string_list_entity(intent: RouterIntent, key: str) -> list[str]:
    value = intent.entities.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    try:
        UUID(str(value))
    except ValueError:
        return []
    return [str(value)]


def _follow_up_text(missing_fields: list[str]) -> str:
    return "Please provide: " + ", ".join(missing_fields) + "."


__all__ = [
    "AGENT_NAME",
    "ALLOWED_EXCEPTION_RISK_FLAGS",
    "ALLOWED_EXCEPTION_STATUSES",
    "AccountInventoryDecision",
    "HIGH_CONFIDENCE_THRESHOLD",
    "build_account_assignment_draft",
    "plan_account_status_exception",
]
