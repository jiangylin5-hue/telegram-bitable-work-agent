from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field


ActionType = Literal["create_record", "update_record", "create_task", "request_reminder"]


@dataclass(frozen=True, slots=True)
class ControlledActionProviderRequest:
    query: str
    requested_action: ActionType
    evidence: tuple[str, ...]
    allowed_target_codes: tuple[str, ...]
    allowed_field_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ControlledActionProviderResult:
    status: Literal["proposed", "denied", "unavailable"]
    action_type: ActionType | None
    target_code: str | None
    proposed_values: dict[str, Any]
    reminder_text: str | None
    reason: str
    usage: dict[str, int]


class _ProviderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    decision: Literal["propose", "deny"]
    action_type: ActionType | None
    target_code: str | None
    proposed_values: dict[str, Any]
    reminder_text: str | None = Field(default=None, max_length=500)
    reason: str = Field(min_length=1, max_length=500)


class OpenRouterControlledActionProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model_name: str | None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key.strip() if isinstance(api_key, str) else None
        self._base_url = (
            base_url.strip().rstrip("/") if isinstance(base_url, str) else None
        )
        self._model_name = model_name.strip() if isinstance(model_name, str) else None
        self._http_client = http_client

    def propose(
        self,
        request: ControlledActionProviderRequest,
        *,
        timeout_seconds: float = 60.0,
    ) -> ControlledActionProviderResult:
        if not self._api_key or not self._base_url or not self._model_name:
            return _unavailable("provider_not_configured")
        _validate_request(request)
        body = {
            "model": self._model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是受权限约束的多维表格动作规划器。只能使用给定证据、target code "
                        "和字段 key。你只能提出待确认动作，不能声称已经写入、创建、更新或发送。"
                        "给定的 target code 和字段 key 已经由后端完成权限过滤；只要证据足以定位"
                        "目标，就可以提出草稿，不要因为上游回答提到‘只读’而拒绝。"
                        "一个用户 Query 可能包含多个动作，本次只处理 requested_action 和当前"
                        "候选 target，不要因为 Query 还包含其他动作而拒绝当前动作。"
                        "如果信息不足、目标不唯一、字段不在白名单或请求冲突，decision 必须为 deny。"
                        "只返回符合 JSON Schema 的对象。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": request.query,
                            "requested_action": request.requested_action,
                            "allowed_target_codes": request.allowed_target_codes,
                            "allowed_field_keys": request.allowed_field_keys,
                            "evidence": request.evidence,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            "response_format": _response_format(request),
            "provider": {"require_parameters": True},
            "max_tokens": 1200,
            "temperature": 0,
        }
        for attempt in range(2):
            try:
                response = self._post(body, timeout_seconds)
                response.raise_for_status()
                payload = _ProviderPayload.model_validate_json(
                    _response_content(response)
                )
                usage = _usage(response)
                return _validate_payload(payload, request, usage)
            except (httpx.HTTPError, ValueError, TypeError):
                if attempt == 0:
                    body["messages"] = [
                        *body["messages"],  # type: ignore[index]
                        {
                            "role": "system",
                            "content": (
                                "上一次输出未通过严格 schema 或权限校验。重新生成一次："
                                "propose 时 action_type/target_code 必须来自白名单，"
                                "非提醒动作必须填写所有 allowed_field_keys；"
                                "deny 时 action_type、target_code、reminder_text 为 null，"
                                "proposed_values 必须为空对象。"
                            ),
                        },
                    ]
                    continue
                return _unavailable("provider_response_invalid_after_retry")
        return _unavailable("provider_response_invalid_after_retry")

    def _post(self, body: dict[str, object], timeout_seconds: float) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        timeout = httpx.Timeout(timeout_seconds)
        if self._http_client is not None:
            return self._http_client.post(url, headers=headers, json=body, timeout=timeout)
        with httpx.Client() as client:
            return client.post(url, headers=headers, json=body, timeout=timeout)


def _validate_request(request: ControlledActionProviderRequest) -> None:
    if (
        not request.query.strip()
        or request.query != request.query.strip()
        or not 1 <= len(request.evidence) <= 12
        or not request.allowed_target_codes
        or len(set(request.allowed_target_codes)) != len(request.allowed_target_codes)
        or len(set(request.allowed_field_keys)) != len(request.allowed_field_keys)
    ):
        raise ValueError("controlled_action_provider_input_invalid")


def _validate_payload(
    payload: _ProviderPayload,
    request: ControlledActionProviderRequest,
    usage: dict[str, int],
) -> ControlledActionProviderResult:
    if payload.decision == "deny":
        if (
            payload.action_type is not None
            or payload.target_code is not None
            or any(value is not None for value in payload.proposed_values.values())
            or payload.reminder_text is not None
        ):
            raise ValueError("controlled_action_denial_payload_invalid")
        return ControlledActionProviderResult(
            status="denied",
            action_type=None,
            target_code=None,
            proposed_values={},
            reminder_text=None,
            reason=payload.reason,
            usage=usage,
        )
    if (
        payload.action_type != request.requested_action
        or payload.target_code not in request.allowed_target_codes
        or not set(payload.proposed_values).issubset(request.allowed_field_keys)
    ):
        raise ValueError("controlled_action_provider_scope_invalid")
    if payload.action_type == "request_reminder":
        if not payload.reminder_text or payload.proposed_values:
            raise ValueError("controlled_action_reminder_invalid")
    elif (
        payload.reminder_text is not None
        or set(payload.proposed_values) != set(request.allowed_field_keys)
        or any(not _is_usable_proposed_value(value) for value in payload.proposed_values.values())
    ):
        raise ValueError("controlled_action_values_invalid")
    return ControlledActionProviderResult(
        status="proposed",
        action_type=payload.action_type,
        target_code=payload.target_code,
        proposed_values=dict(payload.proposed_values),
        reminder_text=payload.reminder_text,
        reason=payload.reason,
        usage=usage,
    )


def _response_format(request: ControlledActionProviderRequest) -> dict[str, object]:
    action_values = [request.requested_action]
    target_values = list(request.allowed_target_codes)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "controlled_action_proposal",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "decision",
                    "action_type",
                    "target_code",
                    "proposed_values",
                    "reminder_text",
                    "reason",
                ],
                "properties": {
                    "decision": {"type": "string", "enum": ["propose", "deny"]},
                    "action_type": {
                        "anyOf": [
                            {"type": "string", "enum": action_values},
                            {"type": "null"},
                        ]
                    },
                    "target_code": {
                        "anyOf": [
                            {"type": "string", "enum": target_values},
                            {"type": "null"},
                        ]
                    },
                    "proposed_values": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            key: {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "number"},
                                    {"type": "boolean"},
                                    {"type": "null"},
                                ]
                            }
                            for key in request.allowed_field_keys
                        },
                        # Strict structured-output providers require every
                        # declared property. Denials encode each field as null;
                        # the post-validator normalizes that to an empty map.
                        "required": list(request.allowed_field_keys),
                    },
                    "reminder_text": {
                        "anyOf": [
                            {"type": "string", "minLength": 1, "maxLength": 500},
                            {"type": "null"},
                        ]
                    },
                    "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                },
            },
        },
    }


def _is_usable_proposed_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().casefold() not in {
            "",
            "null",
            "none",
            "关联项目",
            "待定",
            "未知",
        }
    return isinstance(value, (int, float, bool))


def _response_content(response: httpx.Response) -> str:
    payload = response.json()
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or len(choices) != 1:
        raise TypeError("controlled_action_provider_response_invalid")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise TypeError("controlled_action_provider_response_invalid")
    return content


def _usage(response: httpx.Response) -> dict[str, int]:
    payload = response.json()
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return {}
    return {
        key: int(value)
        for key, value in usage.items()
        if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
        and isinstance(value, int)
        and value >= 0
    }


def _unavailable(reason: str) -> ControlledActionProviderResult:
    return ControlledActionProviderResult(
        status="unavailable",
        action_type=None,
        target_code=None,
        proposed_values={},
        reminder_text=None,
        reason=reason,
        usage={},
    )


__all__ = [
    "ControlledActionProviderRequest",
    "ControlledActionProviderResult",
    "OpenRouterControlledActionProvider",
]
