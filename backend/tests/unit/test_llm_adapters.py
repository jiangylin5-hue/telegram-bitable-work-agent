import json

from app.adapters.llm_fake import FakeStructuredLLMClient
from app.adapters.llm_openrouter import OpenRouterStructuredLLMClient
from app.agents.interfaces import LLMMessage, StructuredLLMRequest
from app.services.agent_runs import create_agent_run_record


def test_fake_llm_returns_structured_json_without_api_key() -> None:
    client = FakeStructuredLLMClient(
        response={"intent_type": "recharge", "confidence": 0.91},
        model_name="fake-router-v1",
    )
    request = StructuredLLMRequest(
        messages=[LLMMessage(role="user", content="recharge act_1001 100 USD")],
        response_schema={"type": "object"},
        prompt_version="intent-router-v1",
    )

    result = client.generate_json(request)

    assert result.content == {"intent_type": "recharge", "confidence": 0.91}
    assert result.model_name == "fake-router-v1"
    assert result.model_provider == "fake"
    assert result.prompt_version == "intent-router-v1"


def test_openrouter_adapter_uses_injected_http_client_and_parses_json_response() -> None:
    http_client = RecordingHttpClient(
        response_payload={
            "id": "or-request-1",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"intent_type": "report_request", "confidence": 0.88}
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        }
    )
    client = OpenRouterStructuredLLMClient(
        api_key="test-key",
        model_name="openrouter/test-model",
        http_client=http_client,
    )
    request = StructuredLLMRequest(
        messages=[
            LLMMessage(role="system", content="Return JSON."),
            LLMMessage(role="user", content="daily report"),
        ],
        response_schema={"type": "object"},
        prompt_version="report-router-v1",
    )

    result = client.generate_json(request)

    assert result.content == {"intent_type": "report_request", "confidence": 0.88}
    assert result.request_id == "or-request-1"
    assert result.model_name == "openrouter/test-model"
    assert result.model_provider == "openrouter"
    assert http_client.calls[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert http_client.calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert http_client.calls[0]["json"]["response_format"] == {"type": "json_object"}


def test_agent_run_record_captures_model_name_and_prompt_version() -> None:
    request = StructuredLLMRequest(
        messages=[LLMMessage(role="user", content="recharge act_1001 100 USD")],
        response_schema={"type": "object"},
        prompt_version="intent-router-v1",
    )
    result = FakeStructuredLLMClient(
        response={"intent_type": "recharge"},
        model_name="fake-router-v1",
    ).generate_json(request)

    run = create_agent_run_record(
        agent_name="message_intake_router",
        graph_name="stage_02_mock_router",
        trace_id="trace-llm-1",
        request=request,
        result=result,
        tool_calls=[{"tool": "create_service_draft"}],
    )

    assert run.agent_name == "message_intake_router"
    assert run.graph_name == "stage_02_mock_router"
    assert run.model_provider == "fake"
    assert run.model_name == "fake-router-v1"
    assert run.prompt_version == "intent-router-v1"
    assert run.input_summary["message_count"] == 1
    assert run.output_summary == {"intent_type": "recharge"}
    assert run.tool_calls == [{"tool": "create_service_draft"}]
    assert run.status == "succeeded"
    assert run.trace_id == "trace-llm-1"


class RecordingHttpClient:
    def __init__(self, *, response_payload: dict) -> None:
        self.response_payload = response_payload
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return RecordingResponse(self.response_payload)


class RecordingResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload
