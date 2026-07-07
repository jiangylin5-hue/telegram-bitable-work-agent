from app.agents.schemas import (
    DraftAgentContext,
    RouterIntent,
    Stage05DraftCandidate,
)

AGENT_NAME = "recharge_draft_agent"


def build_recharge_draft(
    intent: RouterIntent,
    context: DraftAgentContext,
) -> Stage05DraftCandidate:
    account_hint = _string_entity(intent, "account_hint", "account_id")
    amount = _string_entity(intent, "amount")
    currency = _string_entity(intent, "currency")
    missing_fields = _missing_fields(
        intent,
        required={
            "account_hint": account_hint,
            "amount": amount,
            "currency": currency,
        },
    )
    status = "pending_confirmation" if not missing_fields else "needs_more_info"
    payload: dict[str, object] = {
        "customer_message_summary": context.source_text_summary,
        "provider_execution_allowed": False,
    }
    if account_hint is not None:
        payload["account_hint"] = account_hint
    if amount is not None:
        payload["amount"] = amount
    if currency is not None:
        payload["currency"] = currency
    if missing_fields:
        payload["suggested_follow_up_text"] = _follow_up_text(missing_fields)

    return _candidate(
        intent=intent,
        context=context,
        draft_type="recharge",
        status=status,
        payload=payload,
        payload_summary={
            key: value
            for key, value in {
                "account_hint": account_hint,
                "amount": amount,
                "currency": currency,
            }.items()
            if value is not None
        },
        missing_fields=missing_fields,
    )


def _candidate(
    *,
    intent: RouterIntent,
    context: DraftAgentContext,
    draft_type: str,
    status: str,
    payload: dict[str, object],
    payload_summary: dict[str, object],
    missing_fields: list[str],
) -> Stage05DraftCandidate:
    intent_index = intent.intent_index or 0
    return Stage05DraftCandidate(
        draft_type=draft_type,
        status=status,
        intent_type=intent.intent_type,
        intent_index=intent_index,
        payload=payload,
        payload_summary=payload_summary,
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
        idempotency_key=f"draft:{context.source_message_id}:{draft_type}:{intent_index}",
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
    missing: list[str] = []
    for field, value in required.items():
        if value is None and field not in missing:
            missing.append(field)
    for field in intent.missing_context:
        normalized = "account_hint" if field == "account_id" else field
        if normalized not in missing:
            missing.append(normalized)
    return missing


def _follow_up_text(missing_fields: list[str]) -> str:
    return "Please provide: " + ", ".join(missing_fields) + "."


__all__ = ["AGENT_NAME", "build_recharge_draft"]
