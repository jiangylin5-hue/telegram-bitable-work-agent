import json

import httpx

from app.services.agent_action_provider import (
    ControlledActionProviderRequest,
    OpenRouterControlledActionProvider,
)


def _response(content: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        request=httpx.Request("POST", "https://openrouter.test/chat/completions"),
        json={
            "choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        },
    )


class _Client:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.body = None

    def post(self, url, *, headers, json, timeout):
        self.body = json
        return self.response


class _SequenceClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = iter(responses)
        self.calls = 0

    def post(self, url, *, headers, json, timeout):
        self.calls += 1
        return next(self.responses)


def test_action_provider_returns_allowlisted_task_proposal() -> None:
    client = _Client(
        _response(
            {
                "decision": "propose",
                "action_type": "create_task",
                "target_code": "TASKS",
                "proposed_values": {"title": "回访客户", "priority": "high"},
                "reminder_text": None,
                "reason": "项目已逾期，需要负责人跟进",
            }
        )
    )
    provider = OpenRouterControlledActionProvider(
        api_key="secret",
        base_url="https://openrouter.test/api/v1",
        model_name="test/model",
        http_client=client,
    )

    result = provider.propose(
        ControlledActionProviderRequest(
            query="为逾期项目创建高优先级回访任务",
            requested_action="create_task",
            evidence=("PRJ-003 已逾期，负责人是 U-003",),
            allowed_target_codes=("TASKS",),
            allowed_field_keys=("title", "priority"),
        )
    )

    assert result.status == "proposed"
    assert result.target_code == "TASKS"
    assert result.proposed_values == {"title": "回访客户", "priority": "high"}
    assert result.usage["total_tokens"] == 30
    assert client.body["response_format"]["json_schema"]["strict"] is True
    system_prompt = client.body["messages"][0]["content"]
    assert "已经由后端完成权限过滤" in system_prompt
    assert "本次只处理 requested_action" in system_prompt


def test_action_provider_rejects_model_target_outside_scope() -> None:
    client = _Client(
        _response(
            {
                "decision": "propose",
                "action_type": "create_task",
                "target_code": "FOREIGN",
                "proposed_values": {"title": "越权任务"},
                "reminder_text": None,
                "reason": "错误目标",
            }
        )
    )
    result = OpenRouterControlledActionProvider(
        api_key="secret",
        base_url="https://openrouter.test/api/v1",
        model_name="test/model",
        http_client=client,
    ).propose(
        ControlledActionProviderRequest(
            query="创建任务",
            requested_action="create_task",
            evidence=("可见项目 PRJ-003",),
            allowed_target_codes=("TASKS",),
            allowed_field_keys=("title",),
        )
    )

    assert result.status == "unavailable"
    assert result.proposed_values == {}


def test_action_provider_retries_one_invalid_schema_response() -> None:
    invalid = httpx.Response(
        200,
        request=httpx.Request("POST", "https://openrouter.test/chat/completions"),
        json={"choices": [{"message": {"content": "not-json"}}]},
    )
    client = _SequenceClient([
        invalid,
        _response(
            {
                "decision": "propose",
                "action_type": "update_record",
                "target_code": "MT-014",
                "proposed_values": {"status": "in_progress"},
                "reminder_text": None,
                "reason": "按请求生成待确认状态变更",
            }
        ),
    ])

    result = OpenRouterControlledActionProvider(
        api_key="secret",
        base_url="https://openrouter.test/api/v1",
        model_name="test/model",
        http_client=client,
    ).propose(
        ControlledActionProviderRequest(
            query="把 MT-014 提议改为进行中",
            requested_action="update_record",
            evidence=("MT-014 当前 blocked",),
            allowed_target_codes=("MT-014",),
            allowed_field_keys=("status",),
        )
    )

    assert client.calls == 2
    assert result.status == "proposed"
    assert result.proposed_values == {"status": "in_progress"}


def test_action_provider_can_return_strict_denial_without_fake_field_values() -> None:
    client = _Client(
        _response(
            {
                "decision": "deny",
                "action_type": None,
                "target_code": None,
                "proposed_values": {"status": None},
                "reminder_text": None,
                "reason": "请求包含互相冲突的状态",
            }
        )
    )

    result = OpenRouterControlledActionProvider(
        api_key="secret",
        base_url="https://openrouter.test/api/v1",
        model_name="test/model",
        http_client=client,
    ).propose(
        ControlledActionProviderRequest(
            query="把 MT-017 同时改为 done 和 blocked",
            requested_action="update_record",
            evidence=("MT-017 当前 planned",),
            allowed_target_codes=("MT-017",),
            allowed_field_keys=("status",),
        )
    )

    assert result.status == "denied"
    assert result.proposed_values == {}
    properties = client.body["response_format"]["json_schema"]["schema"]["properties"]
    assert properties["proposed_values"]["required"] == ["status"]
    assert {item["type"] for item in properties["proposed_values"]["properties"]["status"]["anyOf"]} == {
        "string",
        "number",
        "boolean",
        "null",
    }
