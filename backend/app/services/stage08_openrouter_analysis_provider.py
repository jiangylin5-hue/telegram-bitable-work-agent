from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from typing import Literal, TypeAlias

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from app.runtime.stage08_collaboration_contracts import (
    AnalysisDecision,
    AnalysisProviderOutcome,
    CollaborationBudget,
    Stage08CollaborationContractFactory,
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
    "Return exactly one JSON object with answer, citation_ordinals, action, and draft. "
    "Allowed actions are read_only, draft_update, general_advice, and deny. "
    "When the input intent is general_advice, use action general_advice or deny "
    "and return citation_ordinals as an empty array []. "
    "For general_advice, use this exact JSON shape and replace only the answer text: "
    '{\"answer\":\"advice\",\"citation_ordinals\":[],\"action\":\"general_advice\",\"draft\":null}. '
    "For read_only, use this exact JSON shape and replace only the answer text and citation ordinal: "
    '{\"answer\":\"fact\",\"citation_ordinals\":[1],\"action\":\"read_only\",\"draft\":null}. '
    "For draft_update, use this exact JSON shape and replace only the answer, citation ordinal, field key, and value: "
    '{\"answer\":\"proposal\",\"citation_ordinals\":[1],\"action\":\"draft_update\",\"draft\":{\"field_key\":\"status\",\"value\":\"proposed\"}}. '
    "A deny action must also return citation_ordinals as an empty array []. "
    "Use draft_update only when requested_action is draft_update. It requires one "
    "draft object with exactly field_key and value, plus at least one evidence citation. "
    "For every other action, draft must be null. Never claim that a record was "
    "written, created, updated, sent, or completed: a draft is only a proposal "
    "awaiting confirmation."
)
_ZH_SYSTEM_PROMPT = (
    "你是受表格权限约束的数字员工分析器。用户使用中文提问时，必须使用简体中文"
    "（Simplified Chinese）直接回答，不得因为输入是中文而拒答。"
    "只能使用调用方给出的编号证据，不得补充常识、猜测或未授权数据。"
    "必须只返回一个 JSON 对象，字段固定为 answer、citation_ordinals、action、draft。"
    "允许的 action 只有 read_only、draft_update、general_advice、deny。"
    "general_advice 和 deny 的 citation_ordinals 必须为空数组，draft 必须为 null。"
    "read_only 必须引用至少一条真实证据，格式示例："
    '{"answer":"基于证据的中文事实","citation_ordinals":[1],"action":"read_only","draft":null}。'
    "只有 requested_action 为 draft_update 时才能使用 draft_update；此时 draft 必须只含"
    " field_key 和 value，并至少引用一条证据。其他 action 的 draft 必须为 null。"
    "草稿仅是等待用户确认的建议，绝不能声称记录已经写入、创建、更新、发送或完成。"
    "记录编号、字段 key 和需要引用的原始标量值必须保持原样。"
)
_WRITE_COMPLETION_CLAIM_RE = re.compile(
    r"(?:已(?:写入|创建|执行|更新|提交|发送|完成)|已经(?:写入|创建|执行|更新|提交|发送|完成)|"
    r"\b(?:wrote|written|created|executed|updated|submitted|sent|completed)\b)",
    re.IGNORECASE,
)
_HAN_CHARACTER_RE = re.compile(r"[\u3400-\u9fff]")
_CHINESE_LANGUAGE_REFUSAL_RE = re.compile(
    r"(?:cannot answer questions? in chinese|please use english|"
    r"不能(?:用|以)?中文(?:回答|作答)?|请(?:使用|用)英语)",
    re.IGNORECASE,
)
_SOURCE_LOCAL_EVIDENCE_ID_RE = re.compile(
    r"(?m)^\[[^\]\s]{1,120}\s+(?=label=[a-z][a-z0-9_]{0,63}\s+type=)"
)
_CHINESE_GENERAL_ADVICE_FALLBACK = (
    "你好，我在。你可以直接告诉我想讨论什么；打开业务 Base 后，我也可以结合授权数据协助分析。"
)
ProviderEvent: TypeAlias = Literal[
    "invoked", "completed", "usage_metadata_present"
]
ProviderAnalysisAction: TypeAlias = Literal[
    "read_only", "draft_update", "general_advice", "deny"
]
ResponseLanguage: TypeAlias = Literal["zh-Hans", "other"]
_MAX_SEMANTIC_OUTPUT_ATTEMPTS = 2


class _OpenRouterDraftPayload(BaseModel):
    model_config = _STRICT_OUTPUT_CONFIG

    field_key: StrictStr = Field(min_length=1, max_length=120)
    value: object


class _OpenRouterAnalysisPayload(BaseModel):
    model_config = _STRICT_OUTPUT_CONFIG

    answer: StrictStr = Field(min_length=1, max_length=2000)
    citation_ordinals: tuple[StrictInt, ...] = Field(max_length=12)
    action: Literal["read_only", "draft_update", "general_advice", "deny"]
    draft: _OpenRouterDraftPayload | None = None


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
            command_snapshot = _command_snapshot(command)
            prompt, evidence_count, command_intent, allowed_provider_actions = _build_prompt(
                material, command
            )
            requested_action = command_snapshot.requested_action
            response_language = _response_language_for_query(command_snapshot.query)
        except Exception:
            return self._complete(_unavailable("invalid_input"))

        json_body = {
            "model": self._model_name,
            "messages": (
                {"role": "system", "content": _system_prompt_for_language(response_language)},
                {"role": "user", "content": prompt},
            ),
            "response_format": _strict_response_format(evidence_count),
            "provider": {"require_parameters": True},
            "max_tokens": 2200,
        }
        if not self._prompt_is_allowed(prompt):
            return self._complete(_unavailable("invalid_input"))

        response_language_rejected = False
        for _ in range(_MAX_SEMANTIC_OUTPUT_ATTEMPTS):
            try:
                timeout_seconds = _bounded_timeout_seconds(
                    self._remaining_deadline_seconds,
                    validated_budget,
                )
                if timeout_seconds <= 0:
                    return self._complete(
                        _unavailable("analysis_provider_unavailable")
                    )
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
                draft_intent = _validate_payload(
                    payload,
                    command_intent=command_intent,
                    requested_action=requested_action,
                    evidence_count=evidence_count,
                    allowed_provider_actions=allowed_provider_actions,
                    response_language=response_language,
                )
                decision = validate_analysis_decision(
                    AnalysisDecision(
                        answer=payload.answer,
                        citation_ordinals=_canonical_citation_ordinals(
                            payload.citation_ordinals
                        ),
                        action=payload.action,
                        draft_intent=draft_intent,
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
            except ValueError as error:
                if str(error) == "stage09_provider_response_language_invalid":
                    response_language_rejected = True
                continue
            except Exception:
                continue

        if (
            response_language == "zh-Hans"
            and command_intent == "general_advice"
            and response_language_rejected
        ):
            self._notify_action("general_advice")
            return self._complete(
                AnalysisProviderOutcome(
                    status="available",
                    reason_code="none",
                    decision=validate_analysis_decision(
                        AnalysisDecision(
                            answer=_CHINESE_GENERAL_ADVICE_FALLBACK,
                            citation_ordinals=(),
                            action="general_advice",
                            draft_intent=None,
                        )
                    ),
                )
            )
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


def _strict_response_format(evidence_count: int) -> dict[str, object]:
    if type(evidence_count) is not int or not 1 <= evidence_count <= 12:
        raise ValueError("stage08_provider_evidence_count_invalid")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "stage08_analysis_response",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["answer", "citation_ordinals", "action", "draft"],
                "properties": {
                    "answer": {"type": "string", "minLength": 1, "maxLength": 2000},
                    "citation_ordinals": {
                        "type": "array",
                        "maxItems": 12,
                        "items": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": evidence_count,
                        },
                    },
                    "action": {
                        "type": "string",
                        "enum": [
                            "read_only",
                            "draft_update",
                            "general_advice",
                            "deny",
                        ],
                    },
                    "draft": {
                        "anyOf": [
                            {"type": "null"},
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["field_key", "value"],
                                "properties": {
                                    "field_key": {
                                        "type": "string",
                                        "minLength": 1,
                                        "maxLength": 120,
                                    },
                                    "value": {
                                        "anyOf": [
                                            {"type": "string"},
                                            {"type": "number"},
                                            {"type": "boolean"},
                                            {"type": "null"},
                                        ]
                                    },
                                },
                            },
                        ],
                    },
                },
            },
        },
    }


def _response_language_for_query(query: str) -> ResponseLanguage:
    return "zh-Hans" if _HAN_CHARACTER_RE.search(query) else "other"


def _system_prompt_for_language(response_language: ResponseLanguage) -> str:
    if response_language == "zh-Hans":
        return _ZH_SYSTEM_PROMPT
    return _SYSTEM_PROMPT


def _answer_meets_language_requirement(
    answer: str, response_language: ResponseLanguage
) -> bool:
    return response_language != "zh-Hans" or (
        _HAN_CHARACTER_RE.search(answer) is not None
        and _CHINESE_LANGUAGE_REFUSAL_RE.search(answer) is None
    )


def _validate_payload(
    payload: _OpenRouterAnalysisPayload,
    *,
    command_intent: str,
    requested_action: str,
    evidence_count: int,
    allowed_provider_actions: tuple[str, ...] | None = None,
    response_language: ResponseLanguage = "other",
) -> object | None:
    if (
        allowed_provider_actions is not None
        and payload.action not in allowed_provider_actions
    ):
        raise ValueError("stage09_provider_skill_action_invalid")
    if command_intent == "general_advice" and payload.action not in {
        "general_advice",
        "deny",
    }:
        raise ValueError("stage08_provider_action_invalid")
    if command_intent != "general_advice" and payload.action == "general_advice":
        raise ValueError("stage08_provider_action_invalid")
    if not _answer_meets_language_requirement(payload.answer, response_language):
        raise ValueError("stage09_provider_response_language_invalid")
    if any(ordinal > evidence_count for ordinal in payload.citation_ordinals):
        raise ValueError("stage08_provider_citation_invalid")
    if payload.action in {"general_advice", "deny"}:
        if payload.citation_ordinals or payload.draft is not None:
            raise ValueError("stage08_provider_citation_invalid")
        return None
    if payload.action == "read_only":
        if (
            requested_action != "read_only"
            or not payload.citation_ordinals
            or payload.draft is not None
        ):
            raise ValueError("stage08_provider_action_invalid")
        return None
    if requested_action != "draft_update" or payload.draft is None:
        raise ValueError("stage08_provider_action_invalid")
    if not payload.citation_ordinals:
        raise ValueError("stage08_provider_citation_invalid")
    if _WRITE_COMPLETION_CLAIM_RE.search(payload.answer):
        raise ValueError("stage08_provider_completion_claim_invalid")
    return Stage08CollaborationContractFactory.draft_intent(
        field_key=payload.draft.field_key,
        value=payload.draft.value,
    )


def _build_prompt(material: object, command: object) -> tuple[str, int, str, tuple[str, ...] | None]:
    provider_snapshot = _provider_input_snapshot(material)
    outer_material = _material_snapshot(provider_snapshot.material)
    if outer_material.kind != "analysis_material":
        raise TypeError("stage08_provider_material_invalid")
    command_snapshot = _command_snapshot(command)
    evidence = _analysis_evidence(outer_material.payload)
    profile = command_snapshot.skill_profile
    safe_profile = None
    allowed_provider_actions = None
    if profile is not None:
        safe_profile = {
            "primary_skill_id": profile.primary_skill_id,
            "purpose": profile.source_skill,
            "allowed_provider_actions": list(profile.allowed_provider_actions),
            "output_contract": profile.output_contract,
            "confirmation_policy": profile.confirmation_policy,
        }
        allowed_provider_actions = profile.allowed_provider_actions
    return (
        json.dumps(
            {
                "query": command_snapshot.query,
                "intent": command_snapshot.intent,
                "requested_action": command_snapshot.requested_action,
                **({"skill_profile": safe_profile} if safe_profile is not None else {}),
                "citation_policy": {
                    "general_advice": "citation_ordinals must be []",
                    "deny": "citation_ordinals must be []",
                    "no_matching_evidence": (
                        "use action deny with citation_ordinals [] and explicitly say no matching record was found"
                    ),
                    "ordinal_scope": (
                        "citation_ordinals refer only to outer evidence[].ordinal; "
                        "never copy numbers from labels inside evidence[].content"
                    ),
                },
                "answer_policy": {
                    "supporting_records": (
                        "for list or count questions, name every supporting record identifier present in the evidence"
                    ),
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
        allowed_provider_actions,
    )


def _analysis_evidence(payload: object) -> tuple[str, ...]:
    if type(payload) is not tuple or not 1 <= len(payload) <= 12:
        raise TypeError("stage08_provider_material_invalid")
    rendered = tuple(
        _SOURCE_LOCAL_EVIDENCE_ID_RE.sub("[", _render_private_material(item))
        for item in payload
    )
    if any(not item.strip() for item in rendered):
        raise TypeError("stage08_provider_material_invalid")
    return rendered


def _canonical_citation_ordinals(values: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(dict.fromkeys(values))


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
