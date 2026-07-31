from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from threading import BoundedSemaphore
from typing import Annotated, Literal, TypeAlias

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.schemas.agent_specialist_results import (
    ProviderAttemptObservationV1,
    ProviderFailureCode,
    ProviderRole,
    specialist_payload_sha256,
)
from app.services.agent_provider_validation import ProviderValidationError


NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
Sha256Hex = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
Message: TypeAlias = Mapping[str, str]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModelProfileV1(_StrictFrozenModel):
    version: Literal["model-profile.v1"]
    profile_id: NonEmptyStr
    provider: Literal["openrouter-compatible"]
    model_id: NonEmptyStr
    allowed_roles: tuple[ProviderRole, ...] = Field(min_length=1)
    supports_strict_json_schema: StrictBool
    response_language: Literal["zh-Hans", "other"]
    temperature: StrictFloat = Field(ge=0, le=2)
    max_output_tokens: StrictInt = Field(ge=1, le=16_000)
    request_timeout_seconds: StrictInt = Field(ge=1, le=120)
    max_attempts: StrictInt = Field(ge=1, le=2)
    max_concurrency: StrictInt = Field(ge=1, le=32)
    data_policy: Literal["permission-filtered-only"]
    content_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_profile(self) -> "ModelProfileV1":
        if len(set(self.allowed_roles)) != len(self.allowed_roles):
            raise ValueError("model_profile_role_duplicate")
        if not self.supports_strict_json_schema:
            raise ValueError("model_profile_strict_schema_required")
        expected = model_profile_sha256(
            self.model_dump(mode="json", exclude={"content_hash"})
        )
        if self.content_hash != expected:
            raise ValueError("model_profile_hash_mismatch")
        return self


@dataclass(frozen=True, slots=True)
class ProviderGatewayResult:
    status: Literal["completed", "failed"]
    payload: BaseModel | None
    failure_code: ProviderFailureCode | None
    observations: tuple[ProviderAttemptObservationV1, ...]


def model_profile_sha256(value: BaseModel | dict[str, object]) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


class ModelGatewayV1:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        profiles: Mapping[ProviderRole, ModelProfileV1],
        now: Callable[[], datetime],
        http_client: object | None = None,
        sleeper: Callable[[float], None] = lambda _value: None,
        observer: Callable[[ProviderAttemptObservationV1], None] | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise RuntimeError("model_gateway_api_key_missing")
        if not isinstance(base_url, str) or not base_url.strip():
            raise RuntimeError("model_gateway_base_url_invalid")
        if not profiles:
            raise RuntimeError("model_gateway_profiles_missing")
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._profiles = dict(profiles)
        self._now = now
        self._http_client = http_client
        self._sleeper = sleeper
        self._observer = observer
        self._semaphores = {
            role: BoundedSemaphore(profile.max_concurrency)
            for role, profile in self._profiles.items()
        }
        for role, profile in self._profiles.items():
            if role not in profile.allowed_roles:
                raise RuntimeError("model_gateway_profile_role_mismatch")

    def invoke(
        self,
        *,
        role: ProviderRole,
        messages: tuple[Message, ...],
        response_schema: dict[str, object],
        validate: Callable[[str], BaseModel],
        deadline_at: datetime,
    ) -> ProviderGatewayResult:
        profile = self._profiles.get(role)
        if profile is None:
            raise RuntimeError("model_gateway_role_unbound")
        if deadline_at.tzinfo is None or deadline_at.utcoffset() is None:
            raise ValueError("model_gateway_deadline_timezone_required")
        observations: list[ProviderAttemptObservationV1] = []
        repair: tuple[ProviderFailureCode, str, str] | None = None
        semaphore = self._semaphores[role]
        for attempt in range(1, profile.max_attempts + 1):
            remaining = (deadline_at - self._now()).total_seconds()
            if remaining <= 0:
                return ProviderGatewayResult(
                    status="failed",
                    payload=None,
                    failure_code="deadline_exhausted",
                    observations=tuple(observations),
                )
            if not semaphore.acquire(timeout=remaining):
                return ProviderGatewayResult(
                    status="failed",
                    payload=None,
                    failure_code="deadline_exhausted",
                    observations=tuple(observations),
                )
            started = self._now()
            content = ""
            try:
                request_messages = [dict(item) for item in messages]
                if repair is not None:
                    failure_code, path, previous = repair
                    request_messages.append(
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "repair": True,
                                    "failure_code": failure_code,
                                    "validation_path": path,
                                    "previous_output": previous[:4000],
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        }
                    )
                response = self._post(
                    json_body={
                        "model": profile.model_id,
                        "messages": request_messages,
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": f"stage12_{role}_response",
                                "strict": True,
                                "schema": response_schema,
                            },
                        },
                        "provider": {"require_parameters": True},
                        "temperature": profile.temperature,
                        "max_tokens": profile.max_output_tokens,
                    },
                    timeout_seconds=min(
                        float(profile.request_timeout_seconds), remaining
                    ),
                )
                if response.status_code != 200:
                    failure_code = _http_failure_code(response.status_code)
                    observation = self._observation(
                        role=role,
                        profile=profile,
                        attempt=attempt,
                        failure_code=failure_code,
                        started=started,
                        repair=repair is not None,
                    )
                    observations.append(observation)
                    self._notify(observation)
                    if (
                        _retryable_http_status(response.status_code)
                        and attempt < profile.max_attempts
                    ):
                        self._sleeper(0.1 * (2 ** (attempt - 1)))
                        continue
                    return ProviderGatewayResult(
                        status="failed",
                        payload=None,
                        failure_code=failure_code,
                        observations=tuple(observations),
                    )
                content, input_tokens, output_tokens = _response_content(response)
                try:
                    payload = validate(content)
                except ProviderValidationError as exc:
                    observation = self._observation(
                        role=role,
                        profile=profile,
                        attempt=attempt,
                        failure_code=exc.code,
                        started=started,
                        repair=repair is not None,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                    observations.append(observation)
                    self._notify(observation)
                    if _repairable(exc.code) and attempt < profile.max_attempts:
                        repair = (exc.code, exc.path, content)
                        continue
                    return ProviderGatewayResult(
                        status="failed",
                        payload=None,
                        failure_code=exc.code,
                        observations=tuple(observations),
                    )
                observation = self._observation(
                    role=role,
                    profile=profile,
                    attempt=attempt,
                    failure_code=None,
                    started=started,
                    repair=repair is not None,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                observations.append(observation)
                self._notify(observation)
                return ProviderGatewayResult(
                    status="completed",
                    payload=payload,
                    failure_code=None,
                    observations=tuple(observations),
                )
            except httpx.TimeoutException:
                failure_code = "provider_timeout"
            except httpx.HTTPError:
                failure_code = "provider_http_error"
            except Exception:
                failure_code = "provider_http_error"
            finally:
                semaphore.release()
            observation = self._observation(
                role=role,
                profile=profile,
                attempt=attempt,
                failure_code=failure_code,
                started=started,
                repair=repair is not None,
            )
            observations.append(observation)
            self._notify(observation)
            if _retryable(failure_code) and attempt < profile.max_attempts:
                self._sleeper(0.1 * (2 ** (attempt - 1)))
                continue
            return ProviderGatewayResult(
                status="failed",
                payload=None,
                failure_code=failure_code,
                observations=tuple(observations),
            )
        return ProviderGatewayResult(
            status="failed",
            payload=None,
            failure_code="provider_http_error",
            observations=tuple(observations),
        )

    def _post(
        self, *, json_body: dict[str, object], timeout_seconds: float
    ) -> httpx.Response:
        kwargs = {
            "headers": {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            "json": json_body,
            "timeout": httpx.Timeout(timeout_seconds),
        }
        url = f"{self._base_url}/chat/completions"
        if self._http_client is not None:
            return self._http_client.post(url, **kwargs)
        with httpx.Client() as client:
            return client.post(url, **kwargs)

    def _observation(
        self,
        *,
        role: ProviderRole,
        profile: ModelProfileV1,
        attempt: int,
        failure_code: ProviderFailureCode | None,
        started: datetime,
        repair: bool,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> ProviderAttemptObservationV1:
        values = {
            "version": "provider-attempt.v1",
            "role": role,
            "profile_id": profile.profile_id,
            "provider": profile.provider,
            "model_id": profile.model_id,
            "attempt": attempt,
            "status": "completed" if failure_code is None else "failed",
            "failure_code": failure_code,
            "latency_ms": max(0, int((self._now() - started).total_seconds() * 1000)),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "repair": repair,
        }
        values["observation_hash"] = specialist_payload_sha256(values)
        return ProviderAttemptObservationV1.model_validate(values)

    def _notify(self, observation: ProviderAttemptObservationV1) -> None:
        if self._observer is None:
            return
        try:
            self._observer(observation)
        except Exception:
            pass


def _http_failure_code(status_code: int) -> ProviderFailureCode:
    if status_code == 429:
        return "provider_rate_limited"
    if status_code in {402, 403}:
        return "provider_quota_exhausted"
    return "provider_http_error"


def _retryable_http_status(status_code: int) -> bool:
    return status_code == 429 or status_code in {500, 502, 503, 504}


def _retryable(code: ProviderFailureCode) -> bool:
    return code in {
        "provider_timeout",
        "provider_rate_limited",
        "provider_http_error",
    }


def _repairable(code: ProviderFailureCode) -> bool:
    return code in {
        "provider_schema_invalid",
        "provider_semantic_invalid",
        "provider_grounding_invalid",
        "provider_language_invalid",
        "provider_citation_invalid",
    }


def _response_content(response: httpx.Response) -> tuple[str, int | None, int | None]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise httpx.HTTPError("provider_response_invalid")
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise httpx.HTTPError("provider_response_invalid")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise httpx.HTTPError("provider_response_invalid")
    usage = payload.get("usage")
    input_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    output_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    if not isinstance(input_tokens, int):
        input_tokens = None
    if not isinstance(output_tokens, int):
        output_tokens = None
    return content, input_tokens, output_tokens


__all__ = [
    "ModelGatewayV1",
    "ModelProfileV1",
    "ProviderGatewayResult",
    "model_profile_sha256",
]
