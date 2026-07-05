from datetime import datetime, timezone

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
) -> AgentRun:
    now = datetime.now(timezone.utc)
    return AgentRun(
        agent_name=agent_name,
        graph_name=graph_name,
        model_provider=result.model_provider,
        model_name=result.model_name,
        prompt_version=request.prompt_version,
        input_summary={
            "message_count": len(request.messages),
            "roles": [message.role for message in request.messages],
            "response_schema": request.response_schema,
        },
        output_summary=result.content,
        tool_calls=list(tool_calls or []),
        status=status,
        trace_id=trace_id,
        started_at=now,
        completed_at=now,
    )
