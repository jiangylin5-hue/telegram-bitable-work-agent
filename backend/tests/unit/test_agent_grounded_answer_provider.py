from __future__ import annotations

from datetime import UTC, datetime
import json

import httpx
import pytest

from app.services.agent_grounded_answer_provider import (
    GroundedAnswerProviderAdapterV2,
    GroundedAnswerProviderInvocationError,
    build_grounded_composer_profile,
)
from app.services.agent_model_gateway import (
    ModelGatewayV1,
    ModelProfileV1,
    model_profile_sha256,
)
from tests.unit.test_agent_grounded_answer_validation import _plan, _request


NOW = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)


def _profile() -> ModelProfileV1:
    values = {
        "version": "model-profile.v1",
        "profile_id": "composer.zh.grounded.v2",
        "provider": "openrouter-compatible",
        "model_id": "google/gemini-2.5-flash",
        "allowed_roles": ("composer",),
        "supports_strict_json_schema": True,
        "response_language": "zh-Hans",
        "temperature": 0.0,
        "max_output_tokens": 1600,
        "request_timeout_seconds": 25,
        "max_attempts": 2,
        "max_concurrency": 2,
        "data_policy": "permission-filtered-only",
    }
    values["content_hash"] = model_profile_sha256(values)
    return ModelProfileV1.model_validate(values)


def _response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 20},
        },
    )


class _Client:
    def __init__(self, contents: list[str]) -> None:
        self.responses = [_response(item) for item in contents]
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


def _adapter(contents: list[str]):
    client = _Client(contents)
    gateway = ModelGatewayV1(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        profiles={"composer": _profile()},
        now=lambda: NOW,
        http_client=client,
    )
    return (
        GroundedAnswerProviderAdapterV2(
            gateway=gateway,
            now=lambda: NOW,
            deadline_seconds=50,
        ),
        client,
    )


def test_adapter_requests_strict_fixed_schema_and_model_authored_answer() -> None:
    adapter, client = _adapter([_plan().model_dump_json()])

    result = adapter(_request())

    assert result == _plan()
    body = client.requests[0][1]["json"]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["provider"] == {"require_parameters": True}
    assert body["reasoning"] == {"effort": "none"}
    assert "seed" not in body
    assert body["temperature"] == _profile().temperature
    encoded_schema = json.dumps(
        body["response_format"]["json_schema"]["schema"], sort_keys=True
    )
    assert '"additionalProperties": {' not in encoded_schema
    messages = body["messages"]
    assert "完整最终中文回答" in messages[0]["content"]
    assert "不能编造" in messages[0]["content"]
    assert "每个 claim 只出现一次" in messages[0]["content"]
    assert "最少必要" in messages[0]["content"]
    assert "可见 text 或 heading 中输出 handle" in messages[0]["content"]
    assert _request().query in messages[1]["content"]
    assert len(adapter.diagnostics) == 1
    assert adapter.diagnostics[0].validation_error_types == ()


def test_grounded_composer_profile_freezes_tdr_023_qwen_candidate() -> None:
    profile = build_grounded_composer_profile(max_attempts=1)

    assert profile.model_id == "deepseek/deepseek-v3.2"
    assert profile.profile_id == "composer.zh.grounded.deepseek-v3.2.v2"
    assert profile.allowed_roles == ("composer",)
    assert profile.max_attempts == 1
    assert profile.supports_strict_json_schema is True
    assert profile.temperature == 0.1


def test_schema_failure_records_shape_without_raw_output() -> None:
    adapter, _ = _adapter(['{"wrong":"secret-shape"}', '{"wrong":"secret-shape"}'])

    with pytest.raises(GroundedAnswerProviderInvocationError) as captured:
        adapter(_request())

    assert captured.value.code == "provider_schema_invalid"
    assert len(adapter.diagnostics) == 2
    fingerprint = adapter.diagnostics[0]
    assert fingerprint.top_level_type == "object"
    assert fingerprint.top_level_keys == ("wrong",)
    assert fingerprint.response_sha256
    assert "secret-shape" not in fingerprint.model_dump_json()
    assert fingerprint.validation_paths


def test_grounding_failure_is_distinct_and_repaired_once() -> None:
    invented = _plan(text="Atlas 项目的预算为 9 亿元。").model_dump_json()
    adapter, client = _adapter([invented, invented])

    with pytest.raises(GroundedAnswerProviderInvocationError) as captured:
        adapter(_request())

    assert captured.value.code == "provider_grounding_invalid"
    assert len(client.requests) == 2
    assert len(adapter.diagnostics) == 2
    assert all(
        "provider_grounding_invalid" in item.validation_error_types
        for item in adapter.diagnostics
    )
    assert adapter.diagnostics[1].repair is True


def test_schema_repair_can_return_a_valid_grounded_plan() -> None:
    adapter, client = _adapter(['{"wrong":true}', _plan().model_dump_json()])

    result = adapter(_request())

    assert result == _plan()
    assert len(client.requests) == 2
    assert len(adapter.diagnostics) == 2
    assert adapter.diagnostics[0].validation_error_types
    assert adapter.diagnostics[1].validation_error_types == ()
    assert adapter.diagnostics[1].repair is True
