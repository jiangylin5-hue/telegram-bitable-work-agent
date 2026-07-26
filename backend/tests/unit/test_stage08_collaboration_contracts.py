from __future__ import annotations

import json
import pickle
from uuid import UUID

import pytest
from pydantic import ValidationError
from pydantic import TypeAdapter

from app.runtime import stage08_collaboration_contracts as collaboration_contracts
from app.runtime.stage08_collaboration_contracts import (
    AnalysisDecision,
    AssistantQuerySafeCitation,
    AssistantQuerySafeView,
    CollaborationBudget,
    Stage08CollaborationContractFactory,
    UnavailableAnalysisProvider,
    UnavailableContextCompressor,
    validate_analysis_decision,
    validate_assistant_query_safe_view,
)
from app.schemas.stage08_collaboration import (
    AssistantStreamAnswerDelta,
    AssistantStreamDone,
    AssistantStreamEvent,
    AssistantStreamStatus,
)
from app.runtime.stage08_contracts import (
    ExecutionBudget,
    ExecutionPlan,
    ExecutionTicketState,
    ToolInvocation,
)


WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000101")
EMPLOYEE_ID = UUID("00000000-0000-4000-8000-000000000102")
TARGET_ID = UUID("00000000-0000-4000-8000-000000000103")
TRACE_HASH = "stage08:collaboration:" + "a" * 32


def test_stream_event_contract_rejects_unknown_or_unbounded_payload() -> None:
    with pytest.raises(ValidationError):
        AssistantStreamAnswerDelta(
            event="answer_delta",
            sequence=1,
            request_id="req-1",
            text="",
            raw_provider="forbidden",
        )


def test_stream_event_contract_rejects_invalid_phase() -> None:
    with pytest.raises(ValidationError):
        AssistantStreamStatus(
            event="status",
            sequence=1,
            request_id="req-1",
            phase="retrieving_private_material",
        )


@pytest.mark.parametrize("sequence", [0, -1, True])
def test_stream_event_contract_requires_positive_strict_sequence(
    sequence: object,
) -> None:
    with pytest.raises(ValidationError):
        AssistantStreamDone(
            event="done",
            sequence=sequence,
            request_id="req-1",
        )


def test_stream_event_union_rejects_unknown_event() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(AssistantStreamEvent).validate_python(
            {
                "event": "provider_token",
                "sequence": 1,
                "request_id": "req-1",
                "text": "forbidden",
            }
        )


def _command(*, query: str = "请告诉我当前项目风险", action: str = "read_only"):
    return Stage08CollaborationContractFactory.command(
        workspace_id=WORKSPACE_ID,
        employee_id=EMPLOYEE_ID,
        actor_user_id="telegram-user-42",
        intent="mixed",
        query=query,
        requested_action=action,
        target_record_id=TARGET_ID if action == "draft_update" else None,
        idempotency_key="idem-e1-001",
    )


def test_private_command_state_material_and_port_input_are_factory_only() -> None:
    command = _command()
    material = Stage08CollaborationContractFactory.private_material(object())
    provider_input = Stage08CollaborationContractFactory.provider_input(material)
    state = Stage08CollaborationContractFactory.initial_state(command)
    draft_intent = Stage08CollaborationContractFactory.draft_intent(
        field_key="next_action",
        value="安排演示",
    )
    safe_context = Stage08CollaborationContractFactory.safe_execution_context(
        trace_hash=TRACE_HASH
    )
    digest = Stage08CollaborationContractFactory.compressed_digest(
        text="仅本次调用使用的摘要"
    )

    private_values = (
        command,
        material,
        provider_input,
        state,
        draft_intent,
        safe_context,
        digest,
    )
    for value in private_values:
        with pytest.raises(TypeError):
            type(value)()
        with pytest.raises(TypeError):
            pickle.dumps(value)
        with pytest.raises(TypeError):
            json.dumps(value)
        assert not hasattr(value, "__dict__")
        assert "请告诉" not in repr(value)
        assert str(WORKSPACE_ID) not in repr(value)
        assert str(EMPLOYEE_ID) not in repr(value)
        assert str(TARGET_ID) not in repr(value)


def test_draft_intent_carries_exactly_one_json_safe_field_value() -> None:
    intent = Stage08CollaborationContractFactory.draft_intent(
        field_key="next_action",
        value={"label": "安排演示", "priority": 2, "ready": True},
    )

    snapshot = collaboration_contracts._draft_intent_snapshot(intent)

    assert snapshot.field_key == "next_action"
    assert snapshot.value == {"label": "安排演示", "priority": 2, "ready": True}
    with pytest.raises(TypeError):
        pickle.dumps(intent)
    with pytest.raises(TypeError):
        json.dumps(intent)


@pytest.mark.parametrize(
    ("field_key", "value"),
    [
        ("", "value"),
        ("   ", "value"),
        ("prompt", "value"),
        ("Response", "value"),
        ("token", "value"),
        ("next_action", object()),
        ("next_action", ("not", "json")),
        ("next_action", {"api_key": "secret"}),
        ("next_action", {"nested": [{"raw_text": "private"}]}),
        ("next_action", float("nan")),
        ("next_action", float("inf")),
    ],
)
def test_draft_intent_rejects_sensitive_keys_and_non_json_values(
    field_key: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        Stage08CollaborationContractFactory.draft_intent(
            field_key=field_key,
            value=value,
        )


def test_safe_execution_context_is_factory_only_hash_only_and_unforgeable() -> None:
    context = Stage08CollaborationContractFactory.safe_execution_context(
        trace_hash=TRACE_HASH
    )
    snapshot = collaboration_contracts._safe_execution_context_snapshot(context)
    assert snapshot.mode == "stage08_e3_safe"
    assert snapshot.trace_hash == TRACE_HASH
    assert TRACE_HASH not in repr(context)
    with pytest.raises(TypeError):
        type(context)()
    with pytest.raises(TypeError):
        pickle.dumps(context)
    with pytest.raises(TypeError):
        json.dumps(context)

    forged = object.__new__(type(context))
    with pytest.raises(TypeError, match="stage08_safe_execution_context_unavailable"):
        collaboration_contracts._safe_execution_context_snapshot(forged)
    with pytest.raises(ValueError, match="stage08_safe_execution_mode_invalid"):
        Stage08CollaborationContractFactory.safe_execution_context(
            trace_hash=TRACE_HASH,
            mode="forged",
        )
    with pytest.raises(ValueError, match="stage08_safe_execution_trace_invalid"):
        Stage08CollaborationContractFactory.safe_execution_context(
            trace_hash=str(TARGET_ID)
        )


def test_safe_execution_context_cannot_be_supplied_by_plan_or_tool_json() -> None:
    budget = ExecutionBudget(
        max_tool_calls=1,
        max_wall_time_ms=100,
        max_graph_depth=1,
        max_retries=0,
        max_retrieval_chunks=0,
    )
    plan_payload = {
        "ticket_id": "ticket",
        "workspace_id": str(WORKSPACE_ID),
        "employee_id": str(EMPLOYEE_ID),
        "actor": "user:telegram-user-42",
        "action": "record_change_draft.create",
        "trace_id": TRACE_HASH,
        "idempotency_key": "idem-e3-safe",
        "state": ExecutionTicketState.planned,
        "budget": budget.model_dump(),
        "invocations": [],
    }
    with pytest.raises(ValidationError):
        ExecutionPlan.model_validate(
            {**plan_payload, "safe_execution_mode": "stage08_e3_safe"}
        )
    with pytest.raises(ValidationError):
        ToolInvocation.model_validate(
            {
                "tool_name": "record_change_draft.create",
                "input": {},
                "safe_context": {"mode": "stage08_e3_safe", "trace_hash": TRACE_HASH},
            }
        )


def test_safe_execution_summary_has_one_exact_whitelist_shape() -> None:
    context = Stage08CollaborationContractFactory.safe_execution_context(
        trace_hash=TRACE_HASH
    )

    summary = collaboration_contracts._stage08_safe_execution_summary(
        context,
        graph="stage08_collaboration_e3",
        status="succeeded",
        action="record_change_draft.create",
        counts={"draft_count": 1},
        code=None,
        latency_ms=0,
        ticket_present=True,
        draft_present=True,
    )

    assert summary == {
        "graph": "stage08_collaboration_e3",
        "status": "succeeded",
        "action": "record_change_draft.create",
        "counts": {"draft_count": 1},
        "code": None,
        "trace_hash": TRACE_HASH,
        "latency_ms": 0,
        "ticket_present": True,
        "draft_present": True,
    }


def test_spoofed_private_carriers_are_rejected_by_consumers() -> None:
    command = _command()
    material = Stage08CollaborationContractFactory.private_material(object())
    provider_input = Stage08CollaborationContractFactory.provider_input(material)

    forged_command = object.__new__(type(command))
    forged_input = object.__new__(type(provider_input))
    budget = CollaborationBudget()

    with pytest.raises(TypeError, match="collaboration_command_unavailable"):
        Stage08CollaborationContractFactory.initial_state(forged_command)
    with pytest.raises(TypeError, match="provider_input_unavailable"):
        UnavailableContextCompressor().compress(forged_input, budget=budget)
    with pytest.raises(TypeError, match="provider_input_unavailable"):
        UnavailableAnalysisProvider().analyse(
            forged_input,
            command,
            budget=budget,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_graph_depth", 2),
        ("max_parallel_reads", 2),
        ("max_retrieval_chunks", 13),
        ("max_wall_time_ms", 29_999),
        ("max_provider_time_ms", 20_001),
        ("max_retries", 1),
        ("max_graph_depth", True),
        ("max_retries", False),
        ("max_wall_time_ms", -1),
    ],
)
def test_collaboration_budget_accepts_only_exact_strict_values(
    field: str,
    value: object,
) -> None:
    budget = CollaborationBudget()
    assert budget.model_dump() == {
        "max_graph_depth": 3,
        "max_parallel_reads": 3,
        "max_retrieval_chunks": 12,
        "max_wall_time_ms": 30_000,
        "max_provider_time_ms": 20_000,
        "max_retries": 2,
    }
    with pytest.raises(ValidationError):
        CollaborationBudget.model_validate({**budget.model_dump(), field: value})


def test_unavailable_ports_are_strict_and_return_only_unavailable_outcomes() -> None:
    command = _command()
    material = Stage08CollaborationContractFactory.private_material(object())
    provider_input = Stage08CollaborationContractFactory.provider_input(material)
    budget = CollaborationBudget()

    compression = UnavailableContextCompressor().compress(
        provider_input,
        budget=budget,
    )
    analysis = UnavailableAnalysisProvider().analyse(
        provider_input,
        command,
        budget=budget,
    )

    assert compression.status == "unavailable"
    assert compression.reason_code == "compressor_unavailable"
    assert compression.digest is None
    assert analysis.status == "unavailable"
    assert analysis.reason_code == "analysis_provider_unavailable"
    assert analysis.decision is None
    with pytest.raises(TypeError, match="provider_input_unavailable"):
        UnavailableContextCompressor().compress({}, budget=budget)
    with pytest.raises(TypeError, match="provider_input_unavailable"):
        UnavailableAnalysisProvider().analyse({}, command, budget=budget)


@pytest.mark.parametrize(
    "payload",
    [
        {"answer": "ok", "citation_ordinals": (0,), "action": "read_only"},
        {"answer": "ok", "citation_ordinals": (13,), "action": "read_only"},
        {"answer": "ok", "citation_ordinals": (2, 1), "action": "read_only"},
        {"answer": "ok", "citation_ordinals": (1, 1), "action": "read_only"},
        {"answer": "ok", "citation_ordinals": (), "action": "write_now"},
        {"answer": "x" * 2001, "citation_ordinals": (), "action": "read_only"},
        {
            "answer": "00000000-0000-4000-8000-000000000999",
            "citation_ordinals": (),
            "action": "read_only",
        },
        {
            "answer": "ok",
            "citation_ordinals": (),
            "action": "read_only",
            "draft_intent": {"resource_id": str(TARGET_ID)},
        },
    ],
)
def test_analysis_decision_rejects_invalid_or_private_output(payload: dict) -> None:
    with pytest.raises((ValidationError, TypeError, ValueError)):
        AnalysisDecision.model_validate(payload)


def test_analysis_decision_accepts_only_factory_draft_intent_and_rebuilds() -> None:
    draft_intent = Stage08CollaborationContractFactory.draft_intent(
        field_key="status",
        value="pending_follow_up",
    )
    decision = AnalysisDecision(
        answer="已根据当前受控资料形成建议。",
        citation_ordinals=(1, 3, 12),
        action="draft_update",
        draft_intent=draft_intent,
    )
    rebuilt = validate_analysis_decision(decision)
    assert rebuilt.action == "draft_update"
    assert rebuilt.citation_ordinals == (1, 3, 12)
    assert "待跟进" not in repr(rebuilt.draft_intent)

    forged = AnalysisDecision.model_construct(
        answer="ok",
        citation_ordinals=(1,),
        action="read_only",
        draft_intent=None,
    )
    forged.__dict__["authority"] = object()
    with pytest.raises(ValueError, match="analysis_decision_shape_invalid"):
        validate_analysis_decision(forged)


def test_safe_view_is_terminal_strict_frozen_and_reconstructed() -> None:
    citation = AssistantQuerySafeCitation(
        ordinal=1,
        label="retrieved_material",
    )
    view = AssistantQuerySafeView(
        status="completed",
        answer="当前可见证据显示项目正在推进。",
        citations=(citation,),
        degradation_codes=(),
        draft_id=None,
    )
    rebuilt = validate_assistant_query_safe_view(view)
    assert rebuilt == view
    with pytest.raises(ValidationError):
        view.answer = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        AssistantQuerySafeView(
            status="reading",
            answer=None,
            citations=(),
            degradation_codes=(),
            draft_id=None,
        )

    forged_citation = AssistantQuerySafeCitation.model_construct(
        ordinal=1,
        label="retrieved_material",
    )
    forged_citation.__dict__["source_id"] = TARGET_ID
    forged_view = AssistantQuerySafeView.model_construct(
        status="completed",
        answer="ok",
        citations=(forged_citation,),
        degradation_codes=(),
        draft_id=None,
    )
    forged_view.__dict__["private_material"] = object()
    with pytest.raises(ValueError, match="assistant_safe_view_shape_invalid"):
        validate_assistant_query_safe_view(forged_view)


def test_terminal_state_cannot_transition_back_to_nonterminal() -> None:
    state = Stage08CollaborationContractFactory.initial_state(_command())
    cancelled = Stage08CollaborationContractFactory.transition(
        state,
        status="cancelled",
    )
    assert Stage08CollaborationContractFactory.terminal_status(cancelled) == "cancelled"
    with pytest.raises(ValueError, match="collaboration_terminal_transition_invalid"):
        Stage08CollaborationContractFactory.transition(
            cancelled,
            status="reading",
        )


def test_degraded_is_terminal_and_has_one_fixed_safe_view_shape() -> None:
    degraded_view = AssistantQuerySafeView(
        status="degraded",
        answer=None,
        citations=(),
        degradation_codes=("analysis_unavailable",),
        draft_id=None,
    )
    assert validate_assistant_query_safe_view(degraded_view) == degraded_view
    for invalid in (
        {"answer": "fallback answer"},
        {
            "citations": (
                AssistantQuerySafeCitation(
                    ordinal=1,
                    label="retrieved_material",
                ),
            )
        },
        {"degradation_codes": ()},
        {"draft_id": TARGET_ID},
    ):
        payload = degraded_view.model_dump(mode="python")
        payload.update(invalid)
        with pytest.raises(ValidationError):
            AssistantQuerySafeView.model_validate(payload)

    state = Stage08CollaborationContractFactory.transition(
        Stage08CollaborationContractFactory.initial_state(_command()),
        status="degraded",
    )
    assert Stage08CollaborationContractFactory.terminal_status(state) == "degraded"
    with pytest.raises(ValueError, match="collaboration_terminal_transition_invalid"):
        Stage08CollaborationContractFactory.transition(state, status="reading")


def test_private_state_carries_bounded_read_analysis_and_policy_results() -> None:
    state = Stage08CollaborationContractFactory.initial_state(_command(action="draft_update"))
    material = Stage08CollaborationContractFactory.private_material(
        object(),
        kind="retrieval_evidence",
    )
    outcome = Stage08CollaborationContractFactory.read_outcome(
        branch="retrieval",
        status="available",
        reason_code="none",
        material=material,
    )
    state = Stage08CollaborationContractFactory.record_read_outcome(state, outcome)
    decision = AnalysisDecision(
        answer="只使用当前受控材料。",
        citation_ordinals=(1,),
        action="draft_update",
        draft_intent=Stage08CollaborationContractFactory.draft_intent(
            field_key="status",
            value="pending_confirmation",
        ),
    )
    state = Stage08CollaborationContractFactory.record_analysis(state, decision)
    state = Stage08CollaborationContractFactory.record_policy_result(
        state,
        draft_allowed=True,
    )

    assert Stage08CollaborationContractFactory.read_outcome_count(state) == 1
    assert Stage08CollaborationContractFactory.analysis_decision(state) == decision
    assert Stage08CollaborationContractFactory.policy_allows_draft(state) is True
    with pytest.raises(ValueError, match="collaboration_read_branch_duplicate"):
        Stage08CollaborationContractFactory.record_read_outcome(state, outcome)


def test_validation_errors_and_repr_do_not_echo_private_values() -> None:
    secret = "PRIVATE-CUSTOMER-PAYLOAD"
    with pytest.raises(ValueError) as exc_info:
        Stage08CollaborationContractFactory.command(
            workspace_id=WORKSPACE_ID,
            employee_id=EMPLOYEE_ID,
            actor_user_id="telegram-user-42",
            intent="mixed",
            query=secret * 601,
            requested_action="read_only",
            target_record_id=None,
            idempotency_key="idem-e1-002",
        )
    assert secret not in str(exc_info.value)
