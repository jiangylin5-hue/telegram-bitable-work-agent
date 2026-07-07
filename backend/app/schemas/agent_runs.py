from pydantic import BaseModel, Field


class AgentRunRecord(BaseModel):
    id: str
    agent_name: str
    graph_name: str
    model_provider: str
    model_name: str
    prompt_version: str
    status: str
    trace_id: str
    input_summary: dict[str, object]
    output_summary: dict[str, object]
    usage_summary: dict[str, object] = Field(default_factory=dict)
    cost_summary: dict[str, object] | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    created_entity_refs: list[dict[str, object]] = Field(default_factory=list)


class AgentRunListResponse(BaseModel):
    records: list[AgentRunRecord]
