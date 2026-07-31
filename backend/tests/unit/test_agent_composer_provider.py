from __future__ import annotations

from datetime import UTC, datetime
import json

import httpx
import pytest

from app.schemas.agent_specialist_results import (
    ProviderAttemptObservationV1,
    specialist_payload_sha256,
)
from app.services.agent_composer_provider import (
    ComposerProviderAdapterV1,
    ComposerProviderInvocationError,
)
from app.services.agent_composer_v2 import (
    ComposerSectionCandidateV1,
    ComposerSectionOrderingRequestV1,
)
from app.services.agent_model_gateway import (
    ModelGatewayV1,
    ModelProfileV1,
    ProviderGatewayResult,
    model_profile_sha256,
)


NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
SCOPE = "a" * 64
A_HANDLE = "section:sha256:" + "a" * 64
B_HANDLE = "section:sha256:" + "b" * 64
C_HANDLE = "section:sha256:" + "c" * 64


def _request() -> ComposerSectionOrderingRequestV1:
    candidates = (
        ComposerSectionCandidateV1(
            section_handle=A_HANDLE,
            section_kind="facts",
            objective_statuses=("completed",),
            default_rank=0,
            allowed_connector_codes=("direct", "next"),
        ),
        ComposerSectionCandidateV1(
            section_handle=B_HANDLE,
            section_kind="degradation",
            objective_statuses=("degraded",),
            default_rank=1,
            allowed_connector_codes=("direct", "however", "safety_boundary"),
        ),
    )
    values = {
        "version": "composer-section-ordering-request.v1",
        "candidates": tuple(item.model_dump(mode="json") for item in candidates),
        "default_order": (A_HANDLE, B_HANDLE),
        "scope_hash": SCOPE,
        "schema_hash": "b" * 64,
        "field_policy_version": "stage12-field-policy.v2",
        "field_policy_hash": "c" * 64,
    }
    content_hash = specialist_payload_sha256(values)
    return ComposerSectionOrderingRequestV1(
        candidates=candidates,
        default_order=(A_HANDLE, B_HANDLE),
        scope_hash=SCOPE,
        schema_hash="b" * 64,
        field_policy_version="stage12-field-policy.v2",
        field_policy_hash="c" * 64,
        content_hash=content_hash,
    )


def _valid_payload() -> dict[str, object]:
    return {
        "version": "composer-section-ordering-plan.v1",
        "ordered_section_handles": [A_HANDLE, B_HANDLE],
        "connector_by_handle": {A_HANDLE: "direct", B_HANDLE: "however"},
    }


def _observation(*, failure_code=None) -> ProviderAttemptObservationV1:
    values = {
        "version": "provider-attempt.v1",
        "role": "composer",
        "profile_id": "composer.zh.baseline.v1",
        "provider": "openrouter-compatible",
        "model_id": "google/gemini-2.5-flash",
        "attempt": 1,
        "status": "completed" if failure_code is None else "failed",
        "failure_code": failure_code,
        "latency_ms": 12,
        "input_tokens": 20,
        "output_tokens": 8,
        "repair": False,
    }
    values["observation_hash"] = specialist_payload_sha256(values)
    return ProviderAttemptObservationV1.model_validate(values)


class _Gateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        payload = kwargs["validate"](self.content)
        return ProviderGatewayResult(
            status="completed",
            payload=payload,
            failure_code=None,
            observations=(_observation(),),
        )


class _FailedGateway:
    def invoke(self, **_kwargs):
        return ProviderGatewayResult(
            status="failed",
            payload=None,
            failure_code="provider_rate_limited",
            observations=(_observation(failure_code="provider_rate_limited"),),
        )


def _profile() -> ModelProfileV1:
    values = {
        "version": "model-profile.v1",
        "profile_id": "composer.zh.baseline.v1",
        "provider": "openrouter-compatible",
        "model_id": "google/gemini-2.5-flash",
        "allowed_roles": ("composer",),
        "supports_strict_json_schema": True,
        "response_language": "zh-Hans",
        "temperature": 0.0,
        "max_output_tokens": 800,
        "request_timeout_seconds": 25,
        "max_attempts": 2,
        "max_concurrency": 2,
        "data_policy": "permission-filtered-only",
    }
    values["content_hash"] = model_profile_sha256(values)
    return ModelProfileV1.model_validate(values)


def _response(payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        json={
            "choices": [{"message": {"content": json.dumps(payload)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


class _Client:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.responses = [_response(item) for item in payloads]
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


def _real_adapter(payloads: list[dict[str, object]]):
    client = _Client(payloads)
    gateway = ModelGatewayV1(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        profiles={"composer": _profile()},
        now=lambda: NOW,
        http_client=client,
    )
    return ComposerProviderAdapterV1(gateway=gateway, now=lambda: NOW), client


def test_composer_provider_sends_only_bounded_candidates_and_strict_schema() -> None:
    gateway = _Gateway(json.dumps(_valid_payload()))
    adapter = ComposerProviderAdapterV1(gateway=gateway, now=lambda: NOW)

    plan = adapter(_request())

    call = gateway.calls[0]
    assert call["role"] == "composer"
    assert call["response_schema"]["additionalProperties"] is False
    system_text = call["messages"][0]["content"]
    assert "只能重排提供的 section_handle" in system_text
    assert "只能选择候选项提供的 connector" in system_text
    request_text = call["messages"][1]["content"]
    assert request_text == json.dumps(
        _request().model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    for forbidden in (
        "objective_id",
        "claim_id",
        "action_slot_id",
        "evidence_id",
        "record:",
        "field:",
        "query",
        "value",
    ):
        assert forbidden not in request_text
    assert plan.ordered_section_handles == (A_HANDLE, B_HANDLE)
    assert plan.connector_by_handle == {A_HANDLE: "direct", B_HANDLE: "however"}
    assert adapter.observations[0].model_id == "google/gemini-2.5-flash"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "version": "composer-section-ordering-plan.v1",
            "ordered_section_handles": [A_HANDLE],
            "connector_by_handle": {A_HANDLE: "direct"},
        },
        {
            "version": "composer-section-ordering-plan.v1",
            "ordered_section_handles": [A_HANDLE, A_HANDLE],
            "connector_by_handle": {A_HANDLE: "direct"},
        },
        {
            "version": "composer-section-ordering-plan.v1",
            "ordered_section_handles": [A_HANDLE, C_HANDLE],
            "connector_by_handle": {A_HANDLE: "direct", C_HANDLE: "however"},
        },
        {
            "version": "composer-section-ordering-plan.v1",
            "ordered_section_handles": [A_HANDLE, B_HANDLE],
            "connector_by_handle": {A_HANDLE: "direct"},
        },
        {
            "version": "composer-section-ordering-plan.v1",
            "ordered_section_handles": [A_HANDLE, B_HANDLE],
            "connector_by_handle": {
                A_HANDLE: "direct",
                B_HANDLE: "however",
                C_HANDLE: "next",
            },
        },
        {
            "version": "composer-section-ordering-plan.v1",
            "ordered_section_handles": [A_HANDLE, B_HANDLE],
            "connector_by_handle": {A_HANDLE: "direct", B_HANDLE: "next"},
        },
        {
            "version": "composer-section-ordering-plan.v1",
            "ordered_section_handles": [A_HANDLE, B_HANDLE],
            "connector_by_handle": {A_HANDLE: "however", B_HANDLE: "however"},
        },
        {
            "version": "composer-section-ordering-plan.v1",
            "ordered_section_handles": [A_HANDLE, B_HANDLE],
            "connector_by_handle": {A_HANDLE: "direct", B_HANDLE: "direct"},
        },
    ],
    ids=(
        "missing-handle",
        "duplicate-handle",
        "unknown-handle",
        "missing-connector",
        "extra-connector",
        "connector-outside-allowlist",
        "first-not-direct",
        "later-direct",
    ),
)
def test_composer_provider_rejects_invalid_ordering_as_semantic_failure(
    payload: dict[str, object],
) -> None:
    adapter = ComposerProviderAdapterV1(
        gateway=_Gateway(json.dumps(payload)), now=lambda: NOW
    )

    with pytest.raises(
        ComposerProviderInvocationError, match="provider_semantic_invalid"
    ):
        adapter(_request())

    assert adapter.failure_code == "provider_semantic_invalid"


def test_composer_provider_repairs_one_semantic_failure_then_completes() -> None:
    invalid = {
        "version": "composer-section-ordering-plan.v1",
        "ordered_section_handles": [A_HANDLE],
        "connector_by_handle": {A_HANDLE: "direct"},
    }
    adapter, client = _real_adapter([invalid, _valid_payload()])

    plan = adapter(_request())

    assert plan.ordered_section_handles == (A_HANDLE, B_HANDLE)
    assert [item.failure_code for item in adapter.observations] == [
        "provider_semantic_invalid",
        None,
    ]
    assert adapter.observations[1].repair is True
    assert len(client.requests) == 2
    repair_message = client.requests[1][1]["json"]["messages"][-1]
    assert "validation_path" in repair_message["content"]


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"version": "composer-section-ordering-plan.v1"}, "provider_schema_invalid"),
        (
            {
                "version": "composer-section-ordering-plan.v1",
                "ordered_section_handles": [A_HANDLE],
                "connector_by_handle": {A_HANDLE: "direct"},
            },
            "provider_semantic_invalid",
        ),
    ],
)
def test_composer_provider_preserves_failure_code_after_repair_exhaustion(
    payload: dict[str, object], expected_code: str
) -> None:
    adapter, _client = _real_adapter([payload, payload])

    with pytest.raises(ComposerProviderInvocationError, match=expected_code):
        adapter(_request())

    assert adapter.failure_code == expected_code
    assert [item.failure_code for item in adapter.observations] == [
        expected_code,
        expected_code,
    ]


def test_composer_provider_preserves_gateway_failure_taxonomy_and_observation() -> None:
    adapter = ComposerProviderAdapterV1(gateway=_FailedGateway(), now=lambda: NOW)

    with pytest.raises(ComposerProviderInvocationError, match="provider_rate_limited"):
        adapter(_request())

    assert adapter.failure_code == "provider_rate_limited"
    assert adapter.observations[0].failure_code == "provider_rate_limited"
