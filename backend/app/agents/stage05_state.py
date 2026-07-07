from typing import Literal, TypedDict

from app.agents.schemas import RouterResult


Stage05WorkflowStatus = Literal[
    "initialized",
    "agent_running",
    "routed",
    "manual_review",
    "agent_failed",
]


class Stage05WorkflowState(TypedDict):
    trace_id: str
    message_id: str
    customer_id: str
    source_text_summary: str
    context_summary: str | None
    router_result: RouterResult | None
    selected_agents: list[str]
    draft_candidates: list[dict[str, object]]
    account_status_actions: list[dict[str, object]]
    manual_review_reasons: list[str]
    agent_run_ids: list[str]
    created_entity_refs: list[dict[str, object]]
    status: Stage05WorkflowStatus
    errors: list[dict[str, object]]


def new_stage05_workflow_state(
    *,
    trace_id: str,
    message_id: str,
    customer_id: str,
    source_text_summary: str,
    context_summary: str | None = None,
) -> Stage05WorkflowState:
    return {
        "trace_id": trace_id,
        "message_id": message_id,
        "customer_id": customer_id,
        "source_text_summary": source_text_summary,
        "context_summary": context_summary,
        "router_result": None,
        "selected_agents": [],
        "draft_candidates": [],
        "account_status_actions": [],
        "manual_review_reasons": [],
        "agent_run_ids": [],
        "created_entity_refs": [],
        "status": "initialized",
        "errors": [],
    }


__all__ = [
    "Stage05WorkflowState",
    "Stage05WorkflowStatus",
    "new_stage05_workflow_state",
]
