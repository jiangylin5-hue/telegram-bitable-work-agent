from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from threading import Event, Thread

import httpx
import pytest

from app.services.agent_model_gateway import (
    ModelGatewayV1,
    ModelProfileV1,
    model_profile_sha256,
)
from app.services.agent_provider_validation import (
    ProviderValidationError,
    parse_and_validate_provider_response,
)
from pydantic import BaseModel, ConfigDict


NOW = datetime(2026, 7, 30, 8, 0, tzinfo=UTC)


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    answer: str
    evidence_ids: tuple[str, ...]


def _profile() -> ModelProfileV1:
    values = {
        "version": "model-profile.v1",
        "profile_id": "risk.zh.baseline.v1",
        "provider": "openrouter-compatible",
        "model_id": "google/gemini-2.5-flash",
        "allowed_roles": ("risk",),
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


def _response(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


def _validator(content: str):
    return parse_and_validate_provider_response(
        content,
        payload_type=_Payload,
        allowed_evidence_ids=frozenset({"ev-01"}),
        response_language="zh-Hans",
    )


def _gateway(client, *, now=lambda: NOW, observations=None, sleeps=None):
    return ModelGatewayV1(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        profiles={"risk": _profile()},
        http_client=client,
        now=now,
        sleeper=(
            (lambda value: sleeps.append(value))
            if sleeps is not None
            else lambda _value: None
        ),
        observer=(observations.append if observations is not None else None),
    )


def test_gateway_uses_role_bound_model_and_emits_sanitized_observation() -> None:
    client = _Client([_response('{"answer":"存在高风险。","evidence_ids":["ev-01"]}')])
    observations = []
    result = _gateway(client, observations=observations).invoke(
        role="risk",
        messages=({"role": "user", "content": "private evidence"},),
        response_schema={"type": "object"},
        validate=_validator,
        deadline_at=NOW + timedelta(seconds=30),
    )

    assert result.status == "completed"
    assert result.payload.answer == "存在高风险。"
    assert client.requests[0][1]["json"]["model"] == "google/gemini-2.5-flash"
    assert observations[0].status == "completed"
    dumped = json.dumps(observations[0].model_dump(mode="json"), ensure_ascii=False)
    assert "private evidence" not in dumped
    assert "存在高风险" not in dumped


def test_gateway_retries_429_then_completes_inside_deadline() -> None:
    client = _Client(
        [
            _response("{}", status=429),
            _response('{"answer":"存在高风险。","evidence_ids":["ev-01"]}'),
        ]
    )
    observations, sleeps = [], []
    result = _gateway(client, observations=observations, sleeps=sleeps).invoke(
        role="risk",
        messages=({"role": "user", "content": "bounded"},),
        response_schema={"type": "object"},
        validate=_validator,
        deadline_at=NOW + timedelta(seconds=30),
    )
    assert result.status == "completed"
    assert len(client.requests) == 2
    assert [item.failure_code for item in observations] == [
        "provider_rate_limited",
        None,
    ]
    assert sleeps == [0.1]


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_gateway_retries_only_recoverable_server_errors(status: int) -> None:
    client = _Client(
        [
            _response("{}", status=status),
            _response('{"answer":"存在高风险。","evidence_ids":["ev-01"]}'),
        ]
    )

    result = _gateway(client).invoke(
        role="risk",
        messages=({"role": "user", "content": "bounded"},),
        response_schema={"type": "object"},
        validate=_validator,
        deadline_at=NOW + timedelta(seconds=30),
    )

    assert result.status == "completed"
    assert len(client.requests) == 2


def test_gateway_does_not_retry_non_recoverable_http_error() -> None:
    client = _Client(
        [
            _response("{}", status=400),
            _response('{"answer":"不应调用。","evidence_ids":["ev-01"]}'),
        ]
    )

    result = _gateway(client).invoke(
        role="risk",
        messages=({"role": "user", "content": "bounded"},),
        response_schema={"type": "object"},
        validate=_validator,
        deadline_at=NOW + timedelta(seconds=30),
    )

    assert result.failure_code == "provider_http_error"
    assert len(client.requests) == 1


def test_gateway_repairs_schema_once_without_new_evidence() -> None:
    client = _Client(
        [
            _response('{"answer":"缺字段"}'),
            _response('{"answer":"已修复。","evidence_ids":["ev-01"]}'),
        ]
    )
    result = _gateway(client).invoke(
        role="risk",
        messages=({"role": "user", "content": "bounded"},),
        response_schema={"type": "object"},
        validate=_validator,
        deadline_at=NOW + timedelta(seconds=30),
    )
    assert result.status == "completed"
    assert len(client.requests) == 2
    repair_messages = client.requests[1][1]["json"]["messages"]
    assert repair_messages[-1]["role"] == "user"
    assert "validation_path" in repair_messages[-1]["content"]


def test_gateway_does_not_retry_permission_or_exhausted_deadline() -> None:
    client = _Client([_response('{"answer":"建议。","evidence_ids":[]}')])

    def denied(_content):
        raise ProviderValidationError("action_not_allowed", "$.action")

    denied_result = _gateway(client).invoke(
        role="risk",
        messages=({"role": "user", "content": "bounded"},),
        response_schema={"type": "object"},
        validate=denied,
        deadline_at=NOW + timedelta(seconds=30),
    )
    assert denied_result.failure_code == "action_not_allowed"
    assert len(client.requests) == 1

    untouched = _Client([_response("{}")])
    deadline_result = _gateway(untouched).invoke(
        role="risk",
        messages=({"role": "user", "content": "bounded"},),
        response_schema={"type": "object"},
        validate=_validator,
        deadline_at=NOW,
    )
    assert deadline_result.failure_code == "deadline_exhausted"
    assert untouched.requests == []


def test_gateway_fails_closed_for_missing_key_or_unbound_role() -> None:
    with pytest.raises(RuntimeError, match="model_gateway_api_key_missing"):
        ModelGatewayV1(
            api_key=None,
            base_url="https://openrouter.ai/api/v1",
            profiles={"risk": _profile()},
            now=lambda: NOW,
        )
    gateway = _gateway(_Client([]))
    with pytest.raises(RuntimeError, match="model_gateway_role_unbound"):
        gateway.invoke(
            role="daily",
            messages=({"role": "user", "content": "bounded"},),
            response_schema={"type": "object"},
            validate=_validator,
            deadline_at=NOW + timedelta(seconds=30),
        )


def test_gateway_role_semaphore_caps_concurrency() -> None:
    entered = Event()
    release = Event()

    class _BlockingClient:
        def __init__(self) -> None:
            self.active = 0
            self.maximum_active = 0

        def post(self, _url, **_kwargs):
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            entered.set()
            release.wait(timeout=2)
            self.active -= 1
            return _response('{"answer":"存在高风险。","evidence_ids":["ev-01"]}')

    values = _profile().model_dump(mode="json", exclude={"content_hash"})
    values["allowed_roles"] = tuple(values["allowed_roles"])
    values["max_concurrency"] = 1
    values["content_hash"] = model_profile_sha256(values)
    profile = ModelProfileV1.model_validate(values)
    client = _BlockingClient()
    gateway = ModelGatewayV1(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        profiles={"risk": profile},
        http_client=client,
        now=lambda: NOW,
    )

    def call() -> None:
        gateway.invoke(
            role="risk",
            messages=({"role": "user", "content": "bounded"},),
            response_schema={"type": "object"},
            validate=_validator,
            deadline_at=NOW + timedelta(seconds=30),
        )

    first = Thread(target=call)
    second = Thread(target=call)
    first.start()
    assert entered.wait(timeout=1)
    second.start()
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert client.maximum_active == 1
