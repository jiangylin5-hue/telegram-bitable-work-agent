import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.interfaces import (
    LLMMessage,
    StructuredLLMClient,
    StructuredLLMRequest,
    StructuredLLMResult,
)


PROMPT_VERSION = "stage06-live-digital-employee-v1"


class Stage06LiveEmployeeState(TypedDict, total=False):
    action: str
    employee_name: str
    prompt: str
    schema: dict[str, Any]
    records: list[dict[str, Any]]
    record_id: str | None
    skill_evidence: dict[str, Any]
    request: StructuredLLMRequest
    result: StructuredLLMResult
    content: dict[str, Any]


def run_stage06_live_employee(
    *,
    action: str,
    employee_name: str,
    prompt: str | None,
    schema: dict[str, Any],
    records: list[dict[str, Any]],
    record_id: str | None,
    llm_client: StructuredLLMClient,
    skill_evidence: dict[str, Any] | None = None,
) -> StructuredLLMResult:
    graph = _build_graph(llm_client)
    state = graph.invoke(
        {
            "action": action,
            "employee_name": employee_name,
            "prompt": prompt or "",
            "schema": schema,
            "records": records,
            "record_id": record_id,
            "skill_evidence": skill_evidence or {},
        }
    )
    return state["result"]


def _build_graph(llm_client: StructuredLLMClient) -> Any:
    graph = StateGraph(Stage06LiveEmployeeState)
    graph.add_node("prepare_context", _prepare_context)
    graph.add_node("call_openrouter", _call_openrouter(llm_client))
    graph.add_node("validate_output", _validate_output)
    graph.set_entry_point("prepare_context")
    graph.add_edge("prepare_context", "call_openrouter")
    graph.add_edge("call_openrouter", "validate_output")
    graph.add_edge("validate_output", END)
    return graph.compile()


def _prepare_context(state: Stage06LiveEmployeeState) -> Stage06LiveEmployeeState:
    response_schema = _response_schema(state["action"])
    payload = {
        "action": state["action"],
        "employee_name": state["employee_name"],
        "user_prompt": state.get("prompt") or "",
        "schema": state["schema"],
        "records": state["records"],
        "record_id": state.get("record_id"),
        "skill_evidence": state.get("skill_evidence", {}),
        "response_schema": response_schema,
        "output_template": _output_template(state["action"]),
    }
    request = StructuredLLMRequest(
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "You are a table-bound digital employee. Return exactly one "
                    "valid JSON object and no markdown. "
                    "Use only the provided permission-filtered schema and records. "
                    "Never claim a write was committed. For draft_update, return "
                    "draft.proposed_values only for fields that should be changed. "
                    "The JSON object must satisfy the provided response_schema and "
                    "must use the output_template keys."
                ),
            ),
            LLMMessage(
                role="user",
                content=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        ],
        response_schema=response_schema,
        prompt_version=PROMPT_VERSION,
    )
    return {**state, "request": request}


def _call_openrouter(
    llm_client: StructuredLLMClient,
):
    def node(state: Stage06LiveEmployeeState) -> Stage06LiveEmployeeState:
        result = llm_client.generate_json(state["request"])
        return {**state, "result": result, "content": result.content}

    return node


def _validate_output(state: Stage06LiveEmployeeState) -> Stage06LiveEmployeeState:
    content = state["content"]
    if not isinstance(content.get("answer"), str) or not content["answer"].strip():
        raise ValueError("Stage06 live digital employee response requires answer")
    citations = content.get("citations", [])
    if not isinstance(citations, list):
        raise ValueError("Stage06 live digital employee citations must be a list")
    schema = state.get("schema", {})
    required_record_ids = (
        schema.get("required_citation_record_ids", [])
        if isinstance(schema, dict)
        else []
    )
    if schema.get("strict_citation_validation", False) is True:
        validate_stage06_live_citations(
            citations,
            state.get("records", []),
            required_record_ids=required_record_ids,
        )
    if state["action"] == "draft_update":
        draft = content.get("draft")
        if not isinstance(draft, dict):
            raise ValueError("Stage06 live draft_update requires draft object")
        proposed_values = draft.get("proposed_values")
        if not isinstance(proposed_values, dict) or not proposed_values:
            raise ValueError("Stage06 live draft_update requires proposed_values")
        if state.get("record_id") and str(draft.get("record_id")) != str(state["record_id"]):
            raise ValueError("Stage06 live draft_update returned a different record_id")
    return state


def validate_stage06_live_citations(
    citations: list[object],
    records: list[dict[str, Any]],
    *,
    required_record_ids: object,
) -> None:
    visible_record_ids = {
        record["id"]
        for record in records
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    visible_field_keys = {
        key
        for record in records
        if isinstance(record, dict) and isinstance(record.get("fields"), dict)
        for key in record["fields"]
        if isinstance(key, str)
    }
    cited_record_ids: set[str] = set()
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {
            "record_id",
            "field_keys",
        }:
            raise ValueError("Stage06 live citation shape is invalid")
        record_id = citation.get("record_id")
        field_keys = citation.get("field_keys")
        if (
            not isinstance(record_id, str)
            or record_id not in visible_record_ids
            or not isinstance(field_keys, list)
            or not field_keys
            or any(
                not isinstance(field_key, str)
                or field_key not in visible_field_keys
                for field_key in field_keys
            )
        ):
            raise ValueError("Stage06 live citation visibility is invalid")
        cited_record_ids.add(record_id)
    if isinstance(required_record_ids, list) and not {
        record_id for record_id in required_record_ids if isinstance(record_id, str)
    }.issubset(cited_record_ids):
        raise ValueError("Stage06 live citation coverage is incomplete")


def _response_schema(action: str) -> dict[str, Any]:
    base_schema: dict[str, Any] = {
        "type": "object",
        "required": ["answer", "citations"],
        "properties": {
            "answer": {"type": "string"},
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["record_id", "field_keys"],
                    "additionalProperties": False,
                    "properties": {
                        "record_id": {"type": "string"},
                        "field_keys": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }
    if action == "draft_update":
        base_schema["required"] = ["answer", "citations", "draft"]
        base_schema["properties"]["draft"] = {
            "type": "object",
            "required": ["record_id", "proposed_values"],
            "properties": {
                "record_id": {"type": "string"},
                "proposed_values": {"type": "object"},
            },
        }
    return base_schema


def _output_template(action: str) -> dict[str, Any]:
    template: dict[str, Any] = {
        "answer": "string summary using only visible records",
        "citations": [
            {
                "record_id": "visible record id",
                "field_keys": ["visible_field_key"],
            }
        ],
    }
    if action == "draft_update":
        template["draft"] = {
            "record_id": "target record id",
            "proposed_values": {"status": "new status or another visible writable field"},
        }
    return template
