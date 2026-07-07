from pydantic import ValidationError

from app.agents.interfaces import LLMMessage, StructuredLLMRequest
from app.agents.schemas import RouterResult


ROUTER_PROMPT_VERSION = "stage05-router-v1"
ROUTER_INVALID_OUTPUT_ERROR_CODE = "agent_output_invalid"
ROUTER_INVALID_OUTPUT_WORKFLOW_STATUS = "agent_failed"

INTENT_TO_CHILD_AGENT = {
    "recharge": "recharge_draft_agent",
    "card_binding": "card_binding_draft_agent",
    "bm_invite": "bm_invite_draft_agent",
    "customer_reply": "customer_reply_draft_agent",
    "account_assignment": "account_inventory_agent",
    "account_status_exception": "account_inventory_agent",
}


class RouterOutputInvalid(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_code = ROUTER_INVALID_OUTPUT_ERROR_CODE
        self.workflow_status = ROUTER_INVALID_OUTPUT_WORKFLOW_STATUS


def build_router_request(
    *,
    trace_id: str,
    message_id: str,
    customer_id: str,
    source_text_summary: str,
    context_summary: str | None = None,
    model_name: str | None = None,
) -> StructuredLLMRequest:
    system_prompt = "\n".join(
        [
            "Return JSON only.",
            "Identify multiple intents when one Telegram message contains multiple tasks.",
            "Do not invent account ids, customer ids, payment profiles or statuses.",
            "Mark missing fields explicitly in missing_context.",
            "Use unknown when evidence is insufficient.",
            "Preserve account hints as strings rather than confirmed records.",
            "Do not claim provider actions succeeded.",
        ]
    )
    user_prompt = "\n".join(
        [
            f"trace_id: {trace_id}",
            f"message_id: {message_id}",
            f"customer_id: {customer_id}",
            "source_text_summary:",
            source_text_summary,
            "context_summary:",
            context_summary or "none",
        ]
    )
    return StructuredLLMRequest(
        messages=[
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ],
        response_schema=RouterResult.model_json_schema(),
        prompt_version=ROUTER_PROMPT_VERSION,
        model_name=model_name,
    )


def parse_router_result(payload: object) -> RouterResult:
    if not isinstance(payload, dict):
        raise RouterOutputInvalid("Router output must be a JSON object")
    try:
        return RouterResult.model_validate(payload)
    except ValidationError as exc:
        raise RouterOutputInvalid("Router output schema validation failed") from exc


def select_child_agents(router_result: RouterResult) -> list[str]:
    selected: list[str] = []
    for intent in router_result.intents:
        child_agent = INTENT_TO_CHILD_AGENT.get(intent.intent_type)
        if child_agent is not None and child_agent not in selected:
            selected.append(child_agent)
    return selected


__all__ = [
    "INTENT_TO_CHILD_AGENT",
    "ROUTER_INVALID_OUTPUT_ERROR_CODE",
    "ROUTER_INVALID_OUTPUT_WORKFLOW_STATUS",
    "ROUTER_PROMPT_VERSION",
    "RouterOutputInvalid",
    "build_router_request",
    "parse_router_result",
    "select_child_agents",
]
