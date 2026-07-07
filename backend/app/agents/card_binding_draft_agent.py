import re

from app.agents.schemas import (
    DraftAgentContext,
    RouterIntent,
    Stage05DraftCandidate,
)

AGENT_NAME = "card_binding_draft_agent"
SENSITIVE_PAYMENT_PATTERN = re.compile(r"\b\d{12,19}\b|cvv|cvc", re.IGNORECASE)


def build_card_binding_draft(
    intent: RouterIntent,
    context: DraftAgentContext,
) -> Stage05DraftCandidate:
    account_hint = _string_entity(intent, "account_hint", "account_id")
    payment_profile_hint = _string_entity(intent, "payment_profile_hint", "card_hint")
    sensitive = (
        payment_profile_hint is not None
        and SENSITIVE_PAYMENT_PATTERN.search(payment_profile_hint) is not None
    )
    missing_fields = _missing_fields(
        intent,
        required={
            "account_hint": account_hint,
            "payment_profile_hint": payment_profile_hint,
        },
    )
    risk_flags = list(intent.risk_flags)
    if sensitive and "sensitive_payment_data_detected" not in risk_flags:
        risk_flags.append("sensitive_payment_data_detected")

    status = "manual_review" if sensitive else (
        "pending_confirmation" if not missing_fields else "needs_more_info"
    )
    payload: dict[str, object] = {
        "one_card_one_account_policy": True,
        "provider_execution_allowed": False,
    }
    if account_hint is not None:
        payload["account_hint"] = account_hint
    if payment_profile_hint is not None:
        payload["payment_profile_hint"] = (
            "redacted_sensitive_payment_data" if sensitive else payment_profile_hint
        )
    if missing_fields:
        payload["suggested_follow_up_text"] = _follow_up_text(missing_fields)

    return _candidate(
        intent=intent,
        context=context,
        status=status,
        payload=payload,
        payload_summary={
            key: value
            for key, value in {
                "account_hint": account_hint,
                "payment_profile_hint_present": payment_profile_hint is not None,
            }.items()
            if value is not None
        },
        missing_fields=missing_fields,
        risk_flags=risk_flags,
        review_reason="sensitive payment data detected" if sensitive else None,
    )


def _candidate(
    *,
    intent: RouterIntent,
    context: DraftAgentContext,
    status: str,
    payload: dict[str, object],
    payload_summary: dict[str, object],
    missing_fields: list[str],
    risk_flags: list[str],
    review_reason: str | None,
) -> Stage05DraftCandidate:
    draft_type = "card_binding"
    intent_index = intent.intent_index or 0
    return Stage05DraftCandidate(
        draft_type=draft_type,
        status=status,
        intent_type=intent.intent_type,
        intent_index=intent_index,
        payload=payload,
        payload_summary=payload_summary,
        missing_fields=missing_fields,
        risk_flags=risk_flags,
        confidence=intent.confidence,
        source_message_id=context.source_message_id,
        source_agent_run_id=context.source_agent_run_id,
        customer_id=context.customer_id,
        created_by_type="agent",
        created_by_id=AGENT_NAME,
        agent_name=AGENT_NAME,
        trace_id=context.trace_id,
        idempotency_key=f"draft:{context.source_message_id}:{draft_type}:{intent_index}",
        review_reason=review_reason,
    )


def _string_entity(intent: RouterIntent, *keys: str) -> str | None:
    for key in keys:
        value = intent.entities.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _missing_fields(
    intent: RouterIntent,
    *,
    required: dict[str, str | None],
) -> list[str]:
    missing = [field for field, value in required.items() if value is None]
    for field in intent.missing_context:
        normalized = "account_hint" if field == "account_id" else field
        if normalized not in missing:
            missing.append(normalized)
    return missing


def _follow_up_text(missing_fields: list[str]) -> str:
    return "Please provide: " + ", ".join(missing_fields) + "."


__all__ = ["AGENT_NAME", "build_card_binding_draft"]
