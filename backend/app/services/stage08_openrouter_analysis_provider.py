from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Literal, TypeAlias

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from app.runtime.stage08_collaboration_contracts import (
    AnalysisDecision,
    AnalysisProviderOutcome,
    CollaborationBudget,
    _Stage08CompressedDigest,
    _Stage08PrivateMaterial,
    _command_snapshot,
    _compressed_digest_snapshot,
    _material_snapshot,
    _provider_input_snapshot,
    validate_analysis_decision,
    validate_collaboration_budget,
)
from app.services.stage08_retrieval_provider import (
    _Stage08PrivateEvidence,
    _stage08_private_evidence_fragments,
)


_STRICT_OUTPUT_CONFIG = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    hide_input_in_errors=True,
)
_SYSTEM_PROMPT = (
    "You are a table-bound digital employee analysis provider. "
    "Use only the numbered evidence supplied by the caller. "
    "Return exactly one JSON object with answer, citation_ordinals, and action. "
    "Allowed actions are read_only, general_advice, and deny. "
    "When the input intent is general_advice, use action general_advice or deny "
    "and return citation_ordinals as an empty array []. "
    "A deny action must also return citation_ordinals as an empty array []. "
    "Never propose a draft field, draft value, direct write, or external send. "
    "If a requested action would require a write, use deny."
)
ProviderEvent: TypeAlias = Literal[
    "invoked", "completed", "usage_metadata_present"
]
ProviderAnalysisAction: TypeAlias = Literal[
    "read_only", "general_advice", "deny"
]


class _OpenRouterAnalysisPayload(BaseModel):
    model_config = _STRICT_OUTPUT_CONFIG

    answer: StrictStr = Field(min_length=1, max_length=2000)
    citation_ordinals: tuple[StrictInt, ...] = Field(max_length=12)
    action: Literal["read_only", "general_advice", "deny"]


class OpenRouterStage08AnalysisProvider:
    """Opt-in F evaluator adapter; never installed by default dependencies."""

    __slots__ = (
        "_api_key",
        "_base_url",
        "_http_client",
        "_model_name",
        "_outbound_prompt_guard",
        "_event_observer",
        "_action_observer",
        "_remaining_deadline_seconds",
    )

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model_name: str | None,
        remaining_deadline_seconds: Callable[[], float],
        http_client: httpx.Client | None = None,
        outbound_prompt_guard: Callable[[str], bool] | None = None,
        event_observer: Callable[[ProviderEvent], None] | None = None,
        action_observer: Callable[[ProviderAnalysisAction], None] | None = None,
    ) -> None:
        if not callable(remaining_deadline_seconds):
            raise TypeError("stage08_provider_deadline_probe_invalid")
        self._api_key = api_key.strip() if type(api_key) is str else None
        self._base_url = (
            base_url.strip().rstrip("/") if type(base_url) is str else None
        )
        self._model_name = model_name.strip() if type(model_name) is str else None
        self._remaining_deadline_seconds = remaining_deadline_seconds
        self._http_client = http_client
        self._outbound_prompt_guard = outbound_prompt_guard
        self._event_observer = event_observer
        self._action_observer = action_observer

    def __repr__(self) -> str:
        return "<OpenRouterStage08AnalysisProvider configured>"

    def analyse(
        self,
        material: object,
        command: object,
        *,
        budget: CollaborationBudget,
    ) -> AnalysisProviderOutcome:
        self._notify("invoked")
        validated_budget = validate_collaboration_budget(budget)
        if not self._api_key or not self._base_url or not self._model_name:
            return self._complete(_unavailable("analysis_provider_unavailable"))

        try:
            timeout_seconds = _bounded_timeout_seconds(
                self._remaining_deadline_seconds,
                validated_budget,
            )
            if timeout_seconds <= 0:
                return self._complete(_unavailable("analysis_provider_unavailable"))
            prompt, evidence_count, command_intent = _build_prompt(material, command)
        except Exception:
            return self._complete(_unavailable("invalid_input"))

        json_body = {
            "model": self._model_name,
            "messages": (
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ),
            "response_format": {"type": "json_object"},
        }
        if not self._prompt_is_allowed(prompt):
            return self._complete(_unavailable("invalid_input"))

        try:
            response = self._post(
                json_body=json_body,
                timeout=httpx.Timeout(timeout_seconds),
            )
            response.raise_for_status()
            if _response_has_usage_metadata(response):
                self._notify("usage_metadata_present")
        except (httpx.TimeoutException, httpx.HTTPError):
            return self._complete(_unavailable("analysis_provider_unavailable"))
        except Exception:
            return self._complete(_unavailable("analysis_provider_unavailable"))

        try:
            content = _response_content(response)
            payload = _OpenRouterAnalysisPayload.model_validate_json(content)
            if command_intent == "general_advice" and payload.action not in {
                "general_advice",
                "deny",
            }:
                raise ValueError("stage08_provider_action_invalid")
            if payload.citation_ordinals and (
                command_intent == "general_advice" or payload.action == "deny"
            ):
                raise ValueError("stage08_provider_citation_invalid")
            if any(
                ordinal > evidence_count for ordinal in payload.citation_ordinals
            ):
                raise ValueError("stage08_provider_citation_invalid")
            decision = validate_analysis_decision(
                AnalysisDecision(
                    answer=payload.answer,
                    citation_ordinals=payload.citation_ordinals,
                    action=payload.action,
                    draft_intent=None,
                )
            )
            self._notify_action(payload.action)
            return self._complete(
                AnalysisProviderOutcome(
                    status="available",
                    reason_code="none",
                    decision=decision,
                )
            )
        except Exception:
            return self._complete(_unavailable("invalid_input"))

    def _prompt_is_allowed(self, prompt: str) -> bool:
        if self._outbound_prompt_guard is None:
            return True
        try:
            allowed = self._outbound_prompt_guard(prompt)
        except Exception:
            return False
        return type(allowed) is bool and allowed

    def _complete(self, outcome: AnalysisProviderOutcome) -> AnalysisProviderOutcome:
        self._notify("completed")
        return outcome

    def _notify(self, event: ProviderEvent) -> None:
        if self._event_observer is None:
            return
        try:
            self._event_observer(event)
        except Exception:
            pass

    def _notify_action(self, action: ProviderAnalysisAction) -> None:
        if self._action_observer is None:
            return
        try:
            self._action_observer(action)
        except Exception:
            pass

    def _post(
        self,
        *,
        json_body: dict[str, object],
        timeout: httpx.Timeout,
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        if self._http_client is not None:
            return self._http_client.post(
                url,
                headers=headers,
                json=json_body,
                timeout=timeout,
            )
        with httpx.Client() as client:
            return client.post(
                url,
                headers=headers,
                json=json_body,
                timeout=timeout,
            )


def _bounded_timeout_seconds(
    remaining_deadline_seconds: Callable[[], float],
    budget: CollaborationBudget,
) -> float:
    remaining = remaining_deadline_seconds()
    if type(remaining) not in {int, float} or not math.isfinite(float(remaining)):
        raise TypeError("stage08_provider_deadline_invalid")
    return min(
        max(0.0, float(remaining)),
        budget.max_provider_time_ms / 1000,
    )


def _build_prompt(material: object, command: object) -> tuple[str, int, str]:
    provider_snapshot = _provider_input_snapshot(material)
    outer_material = _material_snapshot(provider_snapshot.material)
    if outer_material.kind != "analysis_material":
        raise TypeError("stage08_provider_material_invalid")
    command_snapshot = _command_snapshot(command)
    evidence = _analysis_evidence(outer_material.payload)
    return (
        json.dumps(
            {
                "query": command_snapshot.query,
                "intent": command_snapshot.intent,
                "requested_action": command_snapshot.requested_action,
                "citation_policy": {
                    "general_advice": "citation_ordinals must be []",
                    "deny": "citation_ordinals must be []",
                },
                "evidence": tuple(
                    {"ordinal": ordinal, "content": content}
                    for ordinal, content in enumerate(evidence, start=1)
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        len(evidence),
        command_snapshot.intent,
    )


def _analysis_evidence(payload: object) -> tuple[str, ...]:
    if type(payload) is not tuple or not 1 <= len(payload) <= 12:
        raise TypeError("stage08_provider_material_invalid")
    rendered = tuple(_render_private_material(item) for item in payload)
    if any(not item.strip() for item in rendered):
        raise TypeError("stage08_provider_material_invalid")
    return rendered


def _render_private_material(value: object) -> str:
    if type(value) is not _Stage08PrivateMaterial:
        raise TypeError("stage08_provider_material_invalid")
    snapshot = _material_snapshot(value)
    return _render_private_payload(snapshot.payload)


def _render_private_payload(value: object) -> str:
    if type(value) is str:
        return value
    if type(value) is _Stage08PrivateMaterial:
        return _render_private_material(value)
    if type(value) is _Stage08CompressedDigest:
        return _compressed_digest_snapshot(value).text
    if type(value) is _Stage08PrivateEvidence:
        return "\n".join(_stage08_private_evidence_fragments(value))
    if type(value) is tuple and 1 <= len(value) <= 12:
        return "\n".join(_render_private_payload(item) for item in value)
    raise TypeError("stage08_provider_material_invalid")


def _response_content(response: httpx.Response) -> str:
    payload = response.json()
    if type(payload) is not dict:
        raise TypeError("stage08_provider_response_invalid")
    choices = payload.get("choices")
    if type(choices) is not list or len(choices) != 1:
        raise TypeError("stage08_provider_response_invalid")
    choice = choices[0]
    if type(choice) is not dict:
        raise TypeError("stage08_provider_response_invalid")
    message = choice.get("message")
    if type(message) is not dict:
        raise TypeError("stage08_provider_response_invalid")
    content = message.get("content")
    if type(content) is not str:
        raise TypeError("stage08_provider_response_invalid")
    return content


def _response_has_usage_metadata(response: httpx.Response) -> bool:
    try:
        payload = response.json()
    except Exception:
        return False
    return type(payload) is dict and payload.get("usage") is not None


def _unavailable(
    reason_code: Literal["analysis_provider_unavailable", "invalid_input"],
) -> AnalysisProviderOutcome:
    return AnalysisProviderOutcome(
        status="unavailable",
        reason_code=reason_code,
        decision=None,
    )
