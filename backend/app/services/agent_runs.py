from datetime import datetime, timezone
from uuid import UUID

from app.agents.interfaces import StructuredLLMRequest, StructuredLLMResult
from app.models.agent import AgentRun


def create_agent_run_record(
    *,
    agent_name: str,
    graph_name: str,
    trace_id: str,
    request: StructuredLLMRequest,
    result: StructuredLLMResult,
    tool_calls: list[dict[str, object]] | None = None,
    status: str = "succeeded",
    message_id: UUID | None = None,
    latency_ms: int | None = None,
    cost_summary: dict[str, object] | None = None,
    created_entity_refs: list[dict[str, object]] | None = None,
    redaction_policy: str = "summary_only",
) -> AgentRun:
    now = datetime.now(timezone.utc)
    return AgentRun(
        agent_name=agent_name,
        graph_name=graph_name,
        model_provider=result.model_provider,
        model_name=result.model_name,
        prompt_version=request.prompt_version,
        input_summary=_input_summary(request, redaction_policy=redaction_policy),
        output_summary=result.content,
        tool_calls=list(tool_calls or []),
        status=status,
        trace_id=trace_id,
        started_at=now,
        completed_at=now,
        message_id=message_id,
        usage_summary=dict(result.usage or {}),
        cost_summary=cost_summary,
        latency_ms=latency_ms,
        error_code=None,
        error_message_redacted=None,
        created_entity_refs=list(created_entity_refs or []),
        redaction_policy=redaction_policy,
    )


def create_failed_agent_run_record(
    *,
    agent_name: str,
    graph_name: str,
    trace_id: str,
    request: StructuredLLMRequest,
    model_provider: str,
    model_name: str,
    error_code: str,
    error_message_redacted: str,
    tool_calls: list[dict[str, object]] | None = None,
    message_id: UUID | None = None,
    latency_ms: int | None = None,
    created_entity_refs: list[dict[str, object]] | None = None,
    redaction_policy: str = "summary_only",
) -> AgentRun:
    now = datetime.now(timezone.utc)
    return AgentRun(
        agent_name=agent_name,
        graph_name=graph_name,
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=request.prompt_version,
        input_summary=_input_summary(request, redaction_policy=redaction_policy),
        output_summary={},
        tool_calls=list(tool_calls or []),
        status="failed",
        trace_id=trace_id,
        started_at=now,
        completed_at=now,
        message_id=message_id,
        usage_summary={},
        cost_summary=None,
        latency_ms=latency_ms,
        error_code=error_code,
        error_message_redacted=error_message_redacted,
        created_entity_refs=list(created_entity_refs or []),
        redaction_policy=redaction_policy,
    )


def _input_summary(
    request: StructuredLLMRequest,
    *,
    redaction_policy: str,
) -> dict[str, object]:
    return {
        "message_count": len(request.messages),
        "roles": [message.role for message in request.messages],
        "response_schema": request.response_schema,
        "redaction_policy": redaction_policy,
    }
