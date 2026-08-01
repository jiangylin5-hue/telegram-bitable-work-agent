from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from threading import Barrier, Lock
import time

import httpx
import pytest

from app.schemas.agent_grounded_answer_v2 import GroundedRenderSlotTextV1
from app.services.agent_grounded_answer_provider import (
    GroundedAnswerProviderAdapterV2,
    GroundedAnswerProviderInvocationError,
    _grounded_slot_system_prompt,
    build_grounded_composer_profile,
    build_isolated_grounded_slot_request,
)
from app.services.agent_model_gateway import (
    ModelGatewayV1,
    ModelProfileV1,
    ProviderGatewayResult,
    model_profile_sha256,
)
from tests.unit.test_agent_grounded_answer_validation import (
    _action_context_request,
    _render_slot_plan,
    _render_slot_request,
    _two_render_slot_request,
)


NOW = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)


def _slot_output(handle: str = "s001", text: str | None = None) -> str:
    return GroundedRenderSlotTextV1(
        slot_handle=handle,
        text=text or "Atlas 项目的任务状态为 blocked。",
    ).model_dump_json()


def test_isolated_slot_request_excludes_query_and_unrelated_slot_context() -> None:
    request = _two_render_slot_request()

    isolated = build_isolated_grounded_slot_request(request, request.render_slots[1])
    payload = isolated.model_dump(mode="json")
    encoded = isolated.model_dump_json()

    assert "query" not in payload
    assert request.query not in encoded
    assert payload["slot"]["slot_handle"] == "s002"
    assert "s001" not in encoded
    assert payload["claims"] == []
    assert payload["citations"] == []
    assert [item["action_handle"] for item in payload["actions"]] == ["a001"]


def test_isolated_action_slot_contains_only_backend_sealed_prerequisites() -> None:
    request = _action_context_request()

    isolated = build_isolated_grounded_slot_request(request, request.render_slots[1])

    assert tuple(item.claim_handle for item in isolated.claims) == ("c001",)
    assert tuple(item.evidence_handle for item in isolated.citations) == ("e001",)
    assert isolated.slot.context_claim_handles == ("c001",)
    assert isolated.slot.context_evidence_handles == ("e001",)


def test_slot_prompt_specializes_action_and_limitation_without_machine_echo() -> None:
    fact_slot = _render_slot_request().render_slots[0]
    action_slot = _two_render_slot_request().render_slots[1]
    limitation_slot = action_slot.model_copy(
        update={"statement_kind": "limitation", "section_kind": "limitations"}
    )

    fact_prompt = _grounded_slot_system_prompt(fact_slot)
    action_prompt = _grounded_slot_system_prompt(action_slot)
    limitation_prompt = _grounded_slot_system_prompt(limitation_slot)

    assert "不得声称已执行、已确认、已发送、已写入或已更新" in fact_prompt
    assert "action.safe_summary" in action_prompt
    assert "不得添加任何主体、字段、状态、英文标识或数字" in action_prompt
    assert "纯中文限制说明" in limitation_prompt
    assert "不得复制 objective_handle、kind、status、reason_code" in limitation_prompt
    assert "当前存在无法完成或降级的部分" in limitation_prompt


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
    adapter, client = _adapter([_slot_output()])

    result = adapter(_render_slot_request())

    assert result == _render_slot_plan()
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
    assert "一个 RenderSlot" in messages[0]["content"]
    assert "不能编造" in messages[0]["content"]
    assert "只能填写 slot_handle 和中文 text" in messages[0]["content"]
    assert "claims、specialist_findings 和 citations" in messages[0]["content"]
    assert _render_slot_request().query not in messages[1]["content"]
    assert len(adapter.diagnostics) == 1
    assert adapter.diagnostics[0].validation_error_types == ()


def test_adapter_uses_single_text_slot_response_contract() -> None:
    adapter, client = _adapter([_slot_output()])

    result = adapter(_render_slot_request())

    assert result == _render_slot_plan()
    schema = client.requests[0][1]["json"]["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]) == {"slot_handle", "text"}
    assert "section_kind" not in schema["properties"]


def test_grounded_composer_profile_freezes_tdr_028_slot_isolation() -> None:
    profile = build_grounded_composer_profile(max_attempts=1)

    assert profile.model_id == "z-ai/glm-5.2"
    assert profile.profile_id == "composer.zh.grounded.glm-5.2.v4"
    assert profile.allowed_roles == ("composer",)
    assert profile.max_attempts == 1
    assert profile.supports_strict_json_schema is True
    assert profile.temperature == 0.1
    assert profile.max_output_tokens == 2400


def test_adapter_sends_only_backend_owned_slot_closure() -> None:
    adapter, client = _adapter([_slot_output()])

    adapter(_render_slot_request())

    request_payload = json.loads(
        client.requests[0][1]["json"]["messages"][1]["content"]
    )
    assert "query" not in request_payload
    assert request_payload["slot"]["claim_handles"] == ["c001"]
    assert request_payload["slot"]["evidence_handles"] == ["e001"]


def test_schema_failure_records_shape_without_raw_output() -> None:
    adapter, _ = _adapter(['{"wrong":"secret-shape"}', '{"wrong":"secret-shape"}'])

    with pytest.raises(GroundedAnswerProviderInvocationError) as captured:
        adapter(_render_slot_request())

    assert captured.value.code == "provider_schema_invalid"
    assert len(adapter.diagnostics) == 2
    fingerprint = adapter.diagnostics[0]
    assert fingerprint.top_level_type == "object"
    assert fingerprint.top_level_keys == ("wrong",)
    assert fingerprint.response_sha256
    assert "secret-shape" not in fingerprint.model_dump_json()
    assert fingerprint.validation_paths


def test_grounding_failure_is_distinct_and_repaired_once() -> None:
    invented = _slot_output("s001", "Atlas 项目的预算为 9 亿元。")
    adapter, client = _adapter([invented, invented])

    with pytest.raises(GroundedAnswerProviderInvocationError) as captured:
        adapter(_render_slot_request())

    assert captured.value.code == "provider_grounding_invalid"
    assert len(client.requests) == 2
    assert len(adapter.diagnostics) == 2
    assert all(
        "provider_grounding_invalid" in item.validation_error_types
        for item in adapter.diagnostics
    )
    assert adapter.diagnostics[1].repair is True


def test_schema_repair_can_return_a_valid_grounded_slot() -> None:
    adapter, client = _adapter(['{"wrong":true}', _slot_output()])

    result = adapter(_render_slot_request())

    assert result == _render_slot_plan()
    assert len(client.requests) == 2
    assert len(adapter.diagnostics) == 2
    assert adapter.diagnostics[0].validation_error_types
    assert adapter.diagnostics[1].validation_error_types == ()
    assert adapter.diagnostics[1].repair is True


class _ConcurrentSlotGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._barrier = Barrier(2)
        self._lock = Lock()
        self.active = 0
        self.max_active = 0

    def invoke(self, **kwargs: object) -> ProviderGatewayResult:
        messages = kwargs["messages"]
        payload = json.loads(messages[1]["content"])
        handle = payload["slot"]["slot_handle"]
        with self._lock:
            self.calls.append(kwargs)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        self._barrier.wait(timeout=2)
        if handle == "s001":
            time.sleep(0.02)
            content = _slot_output("s001")
        else:
            content = _slot_output("s002", "已生成待确认提议，尚未执行。")
        validated = kwargs["validate"](content)
        with self._lock:
            self.active -= 1
        return ProviderGatewayResult(
            status="completed",
            payload=validated,
            failure_code=None,
            observations=(),
        )


def test_adapter_invokes_each_slot_concurrently_with_one_shared_deadline() -> None:
    gateway = _ConcurrentSlotGateway()
    adapter = GroundedAnswerProviderAdapterV2(
        gateway=gateway,
        now=lambda: NOW,
        deadline_seconds=50,
    )

    result = adapter(_two_render_slot_request())

    assert tuple(item.slot_handle for item in result.slot_outputs) == ("s001", "s002")
    assert len(gateway.calls) == 2
    assert gateway.max_active == 2
    deadlines = {item["deadline_at"] for item in gateway.calls}
    assert deadlines == {NOW + timedelta(seconds=50)}
    assert tuple(item.slot_handle for item in adapter.slot_observations) == (
        "s001",
        "s002",
    )
    assert all(item.status == "completed" for item in adapter.slot_observations)
    for call in gateway.calls:
        request_payload = json.loads(call["messages"][1]["content"])
        assert "query" not in request_payload


class _OneSlotFailsGateway:
    def __init__(self) -> None:
        self.call_count = 0

    def invoke(self, **kwargs: object) -> ProviderGatewayResult:
        self.call_count += 1
        payload = json.loads(kwargs["messages"][1]["content"])
        handle = payload["slot"]["slot_handle"]
        if handle == "s002":
            return ProviderGatewayResult(
                status="failed",
                payload=None,
                failure_code="provider_grounding_invalid",
                observations=(),
            )
        validated = kwargs["validate"](_slot_output(handle))
        return ProviderGatewayResult(
            status="completed",
            payload=validated,
            failure_code=None,
            observations=(),
        )


def test_adapter_is_all_or_nothing_when_any_required_slot_fails() -> None:
    gateway = _OneSlotFailsGateway()
    adapter = GroundedAnswerProviderAdapterV2(
        gateway=gateway,
        now=lambda: NOW,
        deadline_seconds=50,
    )

    with pytest.raises(GroundedAnswerProviderInvocationError) as captured:
        adapter(_two_render_slot_request())

    assert captured.value.code == "provider_grounding_invalid"
    assert gateway.call_count == 2
    assert tuple(item.status for item in adapter.slot_observations) == (
        "completed",
        "failed",
    )


def test_adapter_rejects_more_than_three_slots_before_network() -> None:
    gateway = _OneSlotFailsGateway()
    adapter = GroundedAnswerProviderAdapterV2(
        gateway=gateway,
        now=lambda: NOW,
        deadline_seconds=50,
    )
    request = _render_slot_request().model_copy(
        update={"render_slots": _render_slot_request().render_slots * 4}
    )

    with pytest.raises(GroundedAnswerProviderInvocationError) as captured:
        adapter(request)

    assert captured.value.code == "provider_schema_invalid"
    assert gateway.call_count == 0
