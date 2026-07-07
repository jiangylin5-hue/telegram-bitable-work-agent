from app.agents.schemas import (
    DraftAgentContext,
    RouterIntent,
    Stage05DraftCandidate,
)

AGENT_NAME = "customer_reply_draft_agent"


def build_customer_reply_draft(
    intent: RouterIntent,
    context: DraftAgentContext,
) -> Stage05DraftCandidate:
    reply_text = _string_entity(intent, "reply_text", "suggested_reply")
    missing_fields: list[str] = []
    if reply_text is None:
        missing_fields.append("reply_text")
    for field in intent.missing_context:
        if field not in missing_fields:
            missing_fields.append(field)
    status = "pending_confirmation" if not missing_fields else "needs_more_info"
    payload: dict[str, object] = {
        "source_summary": context.source_text_summary,
        "send_allowed_scope": "staging_allowlisted_test_chat_only",
        "send_request_created": False,
    }
    if reply_text is not None:
        payload["reply_text"] = reply_text
    if missing_fields:
        payload["suggested_follow_up_text"] = _follow_up_text(missing_fields)

    intent_index = intent.intent_index or 0
    return Stage05DraftCandidate(
        draft_type="customer_reply",
        status=status,
        intent_type=intent.intent_type,
        intent_index=intent_index,
        payload=payload,
        payload_summary={"reply_text_present": reply_text is not None},
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
        idempotency_key=f"draft:{context.source_message_id}:customer_reply:{intent_index}",
    )


def _string_entity(intent: RouterIntent, *keys: str) -> str | None:
    for key in keys:
        value = intent.entities.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _follow_up_text(missing_fields: list[str]) -> str:
    return "Please provide: " + ", ".join(missing_fields) + "."


__all__ = ["AGENT_NAME", "build_customer_reply_draft"]
