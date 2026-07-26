from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID

import httpx
import pytest

from app.runtime.stage08_collaboration_contracts import (
    CollaborationBudget,
    Stage08CollaborationContractFactory,
    UnavailableAnalysisProvider,
)
from app.services.stage08_collaboration import Stage08CollaborationDependencies
from app.services.stage08_openrouter_analysis_provider import (
    OpenRouterStage08AnalysisProvider,
)


_WORKSPACE_ID = UUID("10000000-0000-4000-8000-000000000001")
_EMPLOYEE_ID = UUID("20000000-0000-4000-8000-000000000002")
_RECORD_ID = UUID("30000000-0000-4000-8000-000000000003")


def _command(
    *,
    intent: str = "business_fact",
    requested_action: str = "read_only",
) -> object:
    return Stage08CollaborationContractFactory.command(
        workspace_id=_WORKSPACE_ID,
        employee_id=_EMPLOYEE_ID,
        actor_user_id="private-actor",
        intent=intent,
        query="只回答当前授权的合成客户事实",
        requested_action=requested_action,
        target_record_id=_RECORD_ID if requested_action == "draft_update" else None,
        idempotency_key="private-idempotency-key",
    )


def _profiled_command() -> object:
    return Stage08CollaborationContractFactory.command(
        workspace_id=_WORKSPACE_ID,
        employee_id=_EMPLOYEE_ID,
        actor_user_id="private-actor",
        intent="business_fact",
        query="只回答当前授权的合成客户事实",
        requested_action="read_only",
        target_record_id=None,
        idempotency_key="private-idempotency-key",
        skill_profile=Stage08CollaborationContractFactory.resolved_skill_profile(
            manifest_version="stage06-larksuite-skills-v1",
            primary_skill_id="platform-tabular-analysis",
            source_skill="lark-sheets",
            selection_mode="explicit",
            supporting_skill_ids=("platform-base", "platform-shared-policy"),
            allowed_intents=("business_fact", "mixed"),
            allowed_provider_actions=("read_only", "deny"),
            manifest_allowed_actions=("record.query", "table.summarize"),
            output_contract="analysis_answer_with_citations",
            confirmation_policy="read_only",
            safe_label="汇总分析",
        ),
    )


def _provider_input(*contents: str) -> object:
    materials = tuple(
        Stage08CollaborationContractFactory.private_material(
            content,
            kind="composite_context",
        )
        for content in contents
    )
    return Stage08CollaborationContractFactory.provider_input(
        Stage08CollaborationContractFactory.private_material(
            materials,
            kind="analysis_material",
        )
    )


def _response_payload(
    *,
    answer: str = "合成客户当前处于方案确认阶段。",
    citation_ordinals: object = (1,),
    action: str = "read_only",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    content: dict[str, object] = {
        "answer": answer,
        "citation_ordinals": citation_ordinals,
        "action": action,
    }
    content.update(extra or {})
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content, ensure_ascii=False),
                }
            }
        ]
    }


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str | None = "test-key",
    remaining: float = 10.0,
    outbound_prompt_guard: Callable[[str], bool] | None = None,
    event_observer: Callable[[str], None] | None = None,
) -> tuple[OpenRouterStage08AnalysisProvider, httpx.Client]:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return (
        OpenRouterStage08AnalysisProvider(
            api_key=api_key,
            base_url="https://synthetic.openrouter.invalid/api/v1",
            model_name="synthetic/model",
            remaining_deadline_seconds=lambda: remaining,
            http_client=client,
            outbound_prompt_guard=outbound_prompt_guard,
            event_observer=event_observer,
        ),
        client,
    )


def test_outbound_prompt_guard_blocks_transport_with_fixed_outcome() -> None:
    transport_called = False
    guard_results: list[bool] = []
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal transport_called
        transport_called = True
        return httpx.Response(200, request=request, json=_response_payload())

    def guard(prompt: str) -> bool:
        safe = "f2_private_hidden_content" not in prompt
        guard_results.append(safe)
        return safe

    provider, client = _provider(
        handler,
        outbound_prompt_guard=guard,
        event_observer=events.append,
    )
    try:
        outcome = provider.analyse(
            _provider_input("f2_private_hidden_content"),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
    assert transport_called is False
    assert guard_results == [False]
    assert events == ["invoked", "completed"]
    assert "f2_private_hidden_content" not in repr(provider)


def test_telemetry_reports_only_invocation_completion_and_usage_presence() -> None:
    events: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = _response_payload()
        payload["usage"] = {"prompt_tokens": 99, "request_id": "forbidden"}
        return httpx.Response(200, request=request, json=payload)

    provider, client = _provider(handler, event_observer=events.append)
    try:
        outcome = provider.analyse(
            _provider_input("visible synthetic fact"),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "available"
    assert events == ["invoked", "usage_metadata_present", "completed"]
    assert all(event in {"invoked", "completed", "usage_metadata_present"} for event in events)


def test_provider_is_opt_in_and_no_key_never_calls_transport() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request, json=_response_payload())

    provider, client = _provider(handler, api_key=None)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "analysis_provider_unavailable"
    assert outcome.decision is None
    assert called is False
    assert type(Stage08CollaborationDependencies().analysis_provider) is UnavailableAnalysisProvider


def test_invalid_private_input_fails_before_transport() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request, json=_response_payload())

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse({}, _command(), budget=CollaborationBudget())
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
    assert outcome.decision is None
    assert called is False


@pytest.mark.parametrize("failure", ["timeout", "http_5xx"])
def test_transport_failure_maps_to_fixed_unavailable(failure: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(503, request=request, json={"error": "synthetic"})

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "analysis_provider_unavailable"
    assert outcome.decision is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(
            200,
            json=_response_payload(extra={"draft_value": "forbidden"}),
        ),
    ],
)
def test_non_json_or_shape_drift_is_invalid_input(response: httpx.Response) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            response.status_code,
            request=request,
            content=response.content,
            headers=response.headers,
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
    assert outcome.decision is None


@pytest.mark.parametrize(
    ("remaining", "expected"),
    [(3.25, 3.25), (40.0, 20.0)],
)
def test_httpx_transport_timeout_is_bounded_by_deadline_and_budget(
    remaining: float,
    expected: float,
) -> None:
    captured_timeout: dict[str, float] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_timeout.update(request.extensions["timeout"])
        return httpx.Response(200, request=request, json=_response_payload())

    provider, client = _provider(handler, remaining=remaining)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "available"
    assert captured_timeout == {
        "connect": expected,
        "read": expected,
        "write": expected,
        "pool": expected,
    }


def test_zero_remaining_deadline_returns_without_transport() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request, json=_response_payload())

    provider, client = _provider(handler, remaining=0.0)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "analysis_provider_unavailable"
    assert called is False


def test_valid_output_is_a_strict_safe_analysis_decision() -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, request=request, json=_response_payload())

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "available"
    assert outcome.reason_code == "none"
    assert outcome.decision is not None
    assert outcome.decision.answer == "合成客户当前处于方案确认阶段。"
    assert outcome.decision.citation_ordinals == (1,)
    assert outcome.decision.action == "read_only"
    assert outcome.decision.draft_intent is None
    assert captured_body["response_format"] == {
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
                        "items": {"type": "integer"},
                    },
                    "action": {
                        "type": "string",
                        "enum": ["read_only", "draft_update", "general_advice", "deny"],
                    },
                    "draft": {
                        "anyOf": [
                            {"type": "null"},
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["field_key", "value"],
                                "properties": {
                                    "field_key": {"type": "string", "minLength": 1, "maxLength": 120},
                                    "value": {},
                                },
                            },
                        ],
                    },
                },
            },
        },
    }


def test_general_advice_contract_is_explicit_and_empty_citations_are_valid() -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                answer="Use a short next-action checklist.",
                citation_ordinals=(),
                action="general_advice",
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("Synthetic context must not become advice evidence."),
            _command(intent="general_advice"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    outbound = json.dumps(captured_body, ensure_ascii=False)
    assert "general_advice" in outbound
    assert "citation_ordinals" in outbound
    assert "[]" in outbound
    system_instruction = captured_body["messages"][0]["content"]
    assert (
        '{"answer":"advice","citation_ordinals":[],"action":"general_advice","draft":null}'
        in system_instruction
    )
    assert (
        '{"answer":"fact","citation_ordinals":[1],"action":"read_only","draft":null}'
        in system_instruction
    )
    assert (
        '{"answer":"proposal","citation_ordinals":[1],"action":"draft_update","draft":{"field_key":"status","value":"proposed"}}'
        in system_instruction
    )
    assert outcome.status == "available"
    assert outcome.reason_code == "none"
    assert outcome.decision is not None
    assert outcome.decision.citation_ordinals == ()
    assert outcome.decision.action == "general_advice"


def test_business_fact_request_cannot_downgrade_to_uncited_general_advice() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                answer="Use a short next-action checklist.",
                citation_ordinals=(),
                action="general_advice",
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("Synthetic business evidence."),
            _command(intent="business_fact"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
    assert outcome.decision is None


def test_invalid_semantic_payload_retries_once_before_failing_closed() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            payload = _response_payload(
                answer="Use a generic checklist.",
                citation_ordinals=(),
                action="general_advice",
            )
        else:
            payload = _response_payload(
                answer="Use the authorised customer fact.",
                citation_ordinals=(1,),
                action="read_only",
            )
        return httpx.Response(200, request=request, json=payload)

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("Synthetic business evidence."),
            _command(intent="business_fact"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert calls == 2
    assert outcome.status == "available"
    assert outcome.reason_code == "none"
    assert outcome.decision is not None
    assert outcome.decision.action == "read_only"


def test_second_invalid_semantic_payload_fails_closed_after_one_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                answer="Use a generic checklist.",
                citation_ordinals=(),
                action="general_advice",
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("Synthetic business evidence."),
            _command(intent="business_fact"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert calls == 2
    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
    assert outcome.decision is None


def test_general_advice_nonempty_citations_fail_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                citation_ordinals=(1,),
                action="general_advice",
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("Synthetic context must not become advice evidence."),
            _command(intent="general_advice"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
    assert outcome.decision is None


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        ("general_advice", "available"),
        ("deny", "available"),
        ("read_only", "unavailable"),
    ],
)
def test_general_advice_accepts_only_approved_empty_citation_actions(
    action: str,
    expected_status: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                answer="Use a short next-action checklist.",
                citation_ordinals=(),
                action=action,
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("Synthetic context must not become advice evidence."),
            _command(intent="general_advice"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == expected_status
    if expected_status == "available":
        assert outcome.decision is not None
        assert outcome.decision.action == action
        assert outcome.decision.citation_ordinals == ()
    else:
        assert outcome.reason_code == "invalid_input"
        assert outcome.decision is None


@pytest.mark.parametrize("citation_ordinals", [(), (1,)])
def test_deny_never_fabricates_citations(citation_ordinals: tuple[int, ...]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                citation_ordinals=citation_ordinals,
                action="deny",
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("Synthetic context."),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    if citation_ordinals:
        assert outcome.status == "unavailable"
        assert outcome.reason_code == "invalid_input"
        assert outcome.decision is None
    else:
        assert outcome.status == "available"
        assert outcome.decision is not None
        assert outcome.decision.citation_ordinals == ()
        assert outcome.decision.action == "deny"


def test_draft_update_returns_one_sealed_draft_intent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                answer="已提出一个待确认草稿。",
                citation_ordinals=(1,),
                action="draft_update",
                extra={"draft": {"field_key": "status", "value": "in_progress"}},
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(requested_action="draft_update"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "available"
    assert outcome.decision is not None
    assert outcome.decision.action == "draft_update"
    assert outcome.decision.citation_ordinals == (1,)
    assert outcome.decision.draft_intent is not None


@pytest.mark.parametrize(
    "payload",
    [
        _response_payload(action="draft_update"),
        _response_payload(
            action="draft_update",
            citation_ordinals=(),
            extra={"draft": {"field_key": "status", "value": "in_progress"}},
        ),
        _response_payload(citation_ordinals=(2,)),
        _response_payload(
            answer="identifier 30000000-0000-4000-8000-000000000003"
        ),
    ],
)
def test_draft_update_requires_citation_and_one_draft_intent(
    payload: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=payload)

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(requested_action="draft_update"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
    assert outcome.decision is None


def test_draft_update_rejects_claim_that_a_write_already_completed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                answer="已写入客户状态。",
                citation_ordinals=(1,),
                action="draft_update",
                extra={"draft": {"field_key": "status", "value": "in_progress"}},
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("[1] visible synthetic fact"),
            _command(requested_action="draft_update"),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
    assert outcome.decision is None


def test_prompt_is_minimal_and_raw_material_is_not_persisted_or_logged(caplog) -> None:
    visible = "VISIBLE_SYNTHETIC_FACT"
    hidden = "HIDDEN_SYNTHETIC_VALUE"
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, request=request, json=_response_payload())

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input(visible),
            _command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    outbound = json.dumps(captured_body, ensure_ascii=False)
    assert visible in outbound
    assert hidden not in outbound
    assert str(_WORKSPACE_ID) not in outbound
    assert str(_EMPLOYEE_ID) not in outbound
    assert str(_RECORD_ID) not in outbound
    assert "private-actor" not in outbound
    assert "private-idempotency-key" not in outbound
    assert "test-key" not in repr(provider)
    assert visible not in repr(provider)
    assert visible not in outcome.model_dump_json()
    assert caplog.records == []
    with pytest.raises(AttributeError):
        provider.__dict__


def test_profiled_command_sends_only_the_safe_skill_projection_to_openrouter() -> None:
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, request=request, json=_response_payload())

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("visible synthetic fact"),
            _profiled_command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "available"
    prompt = json.loads(captured_body["messages"][1]["content"])
    assert prompt["skill_profile"] == {
        "primary_skill_id": "platform-tabular-analysis",
        "purpose": "lark-sheets",
        "allowed_provider_actions": ["read_only", "deny"],
        "output_contract": "analysis_answer_with_citations",
        "confirmation_policy": "read_only",
    }
    assert "supporting_skill_ids" not in json.dumps(prompt)
    assert "manifest_allowed_actions" not in json.dumps(prompt)


def test_profiled_read_skill_keeps_safe_deny_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(action="deny", citation_ordinals=()),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("visible synthetic fact"),
            _profiled_command(),
            budget=CollaborationBudget(),
        )
    finally:
        client.close()

    assert outcome.status == "available"
    assert outcome.decision is not None
    assert outcome.decision.action == "deny"


def test_profile_rejects_non_deny_action_outside_strict_membership() -> None:
    command = Stage08CollaborationContractFactory.command(
        workspace_id=_WORKSPACE_ID,
        employee_id=_EMPLOYEE_ID,
        actor_user_id="private-actor",
        intent="business_fact",
        query="prepare a controlled draft",
        requested_action="draft_update",
        target_record_id=_RECORD_ID,
        idempotency_key="profile-action-boundary",
        skill_profile=Stage08CollaborationContractFactory.resolved_skill_profile(
            manifest_version="stage06-larksuite-skills-v1",
            primary_skill_id="platform-tabular-analysis",
            source_skill="lark-sheets",
            selection_mode="explicit",
            supporting_skill_ids=("platform-base", "platform-shared-policy"),
            allowed_intents=("business_fact",),
            allowed_provider_actions=("read_only", "deny"),
            manifest_allowed_actions=("record.query",),
            output_contract="analysis_answer_with_citations",
            confirmation_policy="read_only",
            safe_label="汇总分析",
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=_response_payload(
                action="draft_update",
                extra={"draft": {"field_key": "status", "value": "ready"}},
            ),
        )

    provider, client = _provider(handler)
    try:
        outcome = provider.analyse(
            _provider_input("visible synthetic fact"), command, budget=CollaborationBudget()
        )
    finally:
        client.close()

    assert outcome.status == "unavailable"
    assert outcome.reason_code == "invalid_input"
