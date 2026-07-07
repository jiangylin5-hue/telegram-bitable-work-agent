from app.agents.schemas import (
    DraftAgentContext,
    RouterIntent,
    Stage05DraftCandidate,
)

AGENT_NAME = "bm_invite_draft_agent"


def build_bm_invite_draft(
    intent: RouterIntent,
    context: DraftAgentContext,
) -> Stage05DraftCandidate:
    bm_hint = _string_entity(intent, "bm_hint", "bm_id")
    invitee_hint = _string_entity(intent, "invitee_hint", "invitee", "email")
    missing_fields = _missing_fields(
        intent,
        required={"bm_hint": bm_hint, "invitee_hint": invitee_hint},
    )
    status = "pending_confirmation" if not missing_fields else "needs_more_info"
    payload: dict[str, object] = {
        "customer_id": context.customer_id,
        "provider_execution_allowed": False,
    }
    if bm_hint is not None:
        payload["bm_hint"] = bm_hint
    if invitee_hint is not None:
        payload["invitee_hint"] = invitee_hint
    if missing_fields:
        payload["suggested_follow_up_text"] = _follow_up_text(missing_fields)

    intent_index = intent.intent_index or 0
    return Stage05DraftCandidate(
        draft_type="bm_invite",
        status=status,
        intent_type=intent.intent_type,
        intent_index=intent_index,
        payload=payload,
        payload_summary={
            key: value
            for key, value in {
                "bm_hint": bm_hint,
                "invitee_hint": invitee_hint,
            }.items()
            if value is not None
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
        idempotency_key=f"draft:{context.source_message_id}:bm_invite:{intent_index}",
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
        if field not in missing:
            missing.append(field)
    return missing


def _follow_up_text(missing_fields: list[str]) -> str:
    return "Please provide: " + ", ".join(missing_fields) + "."


__all__ = ["AGENT_NAME", "build_bm_invite_draft"]
