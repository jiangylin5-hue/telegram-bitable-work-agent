from __future__ import annotations

import ast
from dataclasses import fields
import json
from pathlib import Path
import pickle
from threading import Lock
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.agents.stage08_collaboration import (
    Stage08CollaborationNodes,
    _SequentialStateUpdate,
    _merge_collaboration_state,
    _sealed_node,
    build_stage08_collaboration_graph,
)
from app.runtime.stage08_collaboration_contracts import (
    AnalysisDecision,
    Stage08CollaborationContractFactory,
)


EXPECTED_NODES = {
    "plan_request",
    "read_composite_context",
    "read_retrieval",
    "mark_general_advice",
    "fan_in",
    "compress_group_context",
    "analyse",
    "policy_gate",
    "materialize_draft",
    "finalize",
}
READ_NODES = {
    "read_composite_context",
    "read_retrieval",
    "mark_general_advice",
}


def _command(*, action: str = "read_only"):
    return Stage08CollaborationContractFactory.command(
        workspace_id=UUID("00000000-0000-4000-8000-000000000201"),
        employee_id=UUID("00000000-0000-4000-8000-000000000202"),
        actor_user_id="telegram-user-e1",
        intent="mixed",
        query="给出当前可见业务状态摘要",
        requested_action=action,
        target_record_id=(
            UUID("00000000-0000-4000-8000-000000000203")
            if action == "draft_update"
            else None
        ),
        idempotency_key=f"idem-{action}",
    )


def _recording_nodes(
    calls: list[str],
    *,
    cancel_at_plan: bool = False,
) -> Stage08CollaborationNodes:
    lock = Lock()

    def callback(name: str):
        def node(state):
            with lock:
                calls.append(name)
            if name == "plan_request" and cancel_at_plan:
                return Stage08CollaborationContractFactory.transition(
                    state,
                    status="cancelled",
                )
            if (
                name == "analyse"
                and Stage08CollaborationContractFactory.requested_action(state)
                == "draft_update"
            ):
                return Stage08CollaborationContractFactory.record_analysis(
                    state,
                    AnalysisDecision(
                        answer="已形成待确认建议。",
                        citation_ordinals=(),
                    action="draft_update",
                    draft_intent=Stage08CollaborationContractFactory.draft_intent(
                        field_key="title",
                        value="形成待确认草稿",
                    ),
                    ),
                )
            if (
                name == "policy_gate"
                and Stage08CollaborationContractFactory.requested_action(state)
                == "draft_update"
            ):
                return Stage08CollaborationContractFactory.record_policy_result(
                    state,
                    draft_allowed=True,
                )
            return state

        return node

    return Stage08CollaborationNodes(
        **{name: callback(name) for name in EXPECTED_NODES}
    )


def test_graph_has_exact_ten_nodes_fixed_edges_and_no_checkpointer() -> None:
    graph = build_stage08_collaboration_graph(_recording_nodes([]))
    drawable = graph.get_graph()
    node_names = set(drawable.nodes) - {"__start__", "__end__"}
    edges = {(edge.source, edge.target) for edge in drawable.edges}

    assert {field.name for field in fields(Stage08CollaborationNodes)} == EXPECTED_NODES
    assert node_names == EXPECTED_NODES
    assert graph.checkpointer is None
    assert {("__start__", "plan_request"), ("finalize", "__end__")} <= edges
    assert {("plan_request", node) for node in READ_NODES} <= edges
    assert {(node, "fan_in") for node in READ_NODES} <= edges
    assert ("fan_in", "compress_group_context") in edges
    assert ("compress_group_context", "analyse") in edges
    assert ("analyse", "policy_gate") in edges
    assert ("policy_gate", "materialize_draft") in edges
    assert ("policy_gate", "finalize") in edges
    assert ("materialize_draft", "finalize") in edges


def test_graph_fans_out_exactly_three_reads_then_fans_in() -> None:
    calls: list[str] = []
    graph = build_stage08_collaboration_graph(_recording_nodes(calls))
    state = Stage08CollaborationContractFactory.initial_state(_command())

    result = graph.invoke(state)

    assert calls[0] == "plan_request"
    assert set(calls[1:4]) == READ_NODES
    assert calls[4:] == [
        "fan_in",
        "compress_group_context",
        "analyse",
        "policy_gate",
        "finalize",
    ]
    assert "materialize_draft" not in calls
    assert result is state


def test_draft_request_takes_only_policy_to_materialize_then_finalize_path() -> None:
    calls: list[str] = []
    graph = build_stage08_collaboration_graph(_recording_nodes(calls))
    state = Stage08CollaborationContractFactory.initial_state(
        _command(action="draft_update")
    )

    graph.invoke(state)

    assert calls[-3:] == ["policy_gate", "materialize_draft", "finalize"]


def test_draft_request_without_explicit_policy_pass_skips_materialization() -> None:
    calls: list[str] = []
    nodes = _recording_nodes(calls)

    def no_decision_policy(state):
        calls.append("policy_gate")
        return state

    nodes = Stage08CollaborationNodes(
        **{
            field.name: (
                no_decision_policy
                if field.name == "policy_gate"
                else getattr(nodes, field.name)
            )
            for field in fields(Stage08CollaborationNodes)
        }
    )
    graph = build_stage08_collaboration_graph(nodes)
    graph.invoke(
        Stage08CollaborationContractFactory.initial_state(
            _command(action="draft_update")
        )
    )

    assert "materialize_draft" not in calls
    assert calls[-1] == "finalize"


def test_cancelled_plan_skips_all_reads_and_actions_and_only_finalizes() -> None:
    calls: list[str] = []
    graph = build_stage08_collaboration_graph(
        _recording_nodes(calls, cancel_at_plan=True)
    )
    state = Stage08CollaborationContractFactory.initial_state(_command())

    result = graph.invoke(state)

    assert calls == ["plan_request", "finalize"]
    assert Stage08CollaborationContractFactory.terminal_status(result) == "cancelled"


def test_graph_rejects_public_dict_as_private_state() -> None:
    graph = build_stage08_collaboration_graph(_recording_nodes([]))
    try:
        graph.invoke({"status": "completed", "private_material": "leak"})
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("public dict must not enter the private graph")


def _state_with_read_outcome(state, *, material_payload: object):
    material = Stage08CollaborationContractFactory.private_material(
        material_payload,
        kind="retrieval_evidence",
    )
    outcome = Stage08CollaborationContractFactory.read_outcome(
        branch="retrieval",
        status="available",
        reason_code="none",
        material=material,
    )
    return Stage08CollaborationContractFactory.record_read_outcome(state, outcome)


def _draft_analysis(state, *, answer: str):
    return Stage08CollaborationContractFactory.record_analysis(
        state,
        AnalysisDecision(
            answer=answer,
            citation_ordinals=(),
            action="draft_update",
            draft_intent=Stage08CollaborationContractFactory.draft_intent(
                field_key="title",
                value="形成待确认草稿",
            ),
        ),
    )


def test_reducer_allows_only_zero_outcome_same_state_seed_noop() -> None:
    state = Stage08CollaborationContractFactory.initial_state(_command())
    assert _merge_collaboration_state(state, state) is state

    state_with_outcome = _state_with_read_outcome(
        state,
        material_payload=object(),
    )
    try:
        _merge_collaboration_state(state_with_outcome, state_with_outcome)
    except ValueError as exc:
        assert str(exc) == "collaboration_parallel_read_conflict"
    else:
        raise AssertionError("same-object duplicate read branch must fail closed")


def test_reducer_rejects_distinct_outcomes_for_the_same_read_branch() -> None:
    state = Stage08CollaborationContractFactory.initial_state(_command())
    left = _state_with_read_outcome(state, material_payload=object())
    right = _state_with_read_outcome(state, material_payload=object())

    try:
        _merge_collaboration_state(left, right)
    except ValueError as exc:
        assert str(exc) == "collaboration_parallel_read_conflict"
    else:
        raise AssertionError("duplicate read branch must fail closed")


def test_reducer_rejects_false_true_policy_conflict() -> None:
    base = _draft_analysis(
        Stage08CollaborationContractFactory.initial_state(
            _command(action="draft_update")
        ),
        answer="建议一",
    )
    denied = Stage08CollaborationContractFactory.record_policy_result(
        base,
        draft_allowed=False,
    )
    allowed = Stage08CollaborationContractFactory.record_policy_result(
        base,
        draft_allowed=True,
    )

    try:
        _merge_collaboration_state(denied, allowed)
    except ValueError as exc:
        assert str(exc) == "collaboration_parallel_policy_conflict"
    else:
        raise AssertionError("policy false/true conflict must fail closed")


def test_reducer_rejects_nonempty_analysis_and_terminal_conflicts() -> None:
    base = Stage08CollaborationContractFactory.initial_state(
        _command(action="draft_update")
    )
    first = _draft_analysis(base, answer="建议一")
    second = _draft_analysis(base, answer="建议二")
    try:
        _merge_collaboration_state(first, second)
    except ValueError as exc:
        assert str(exc) == "collaboration_parallel_analysis_conflict"
    else:
        raise AssertionError("different nonempty analysis must fail closed")

    cancelled = Stage08CollaborationContractFactory.transition(
        base,
        status="cancelled",
    )
    failed = Stage08CollaborationContractFactory.transition(
        base,
        status="failed",
    )
    try:
        _merge_collaboration_state(cancelled, failed)
    except ValueError as exc:
        assert str(exc) == "collaboration_parallel_terminal_conflict"
    else:
        raise AssertionError("different terminal states must fail closed")

    degraded = Stage08CollaborationContractFactory.transition(
        base,
        status="degraded",
    )
    assert _merge_collaboration_state(degraded, degraded) is degraded
    try:
        _merge_collaboration_state(degraded, failed)
    except ValueError as exc:
        assert str(exc) == "collaboration_parallel_terminal_conflict"
    else:
        raise AssertionError("degraded/failed terminal conflict must fail closed")


def test_sequential_update_marker_is_factory_only_opaque_and_nonserializable() -> None:
    state = Stage08CollaborationContractFactory.initial_state(_command())
    with pytest.raises(
        TypeError,
        match="collaboration_sequential_update_unavailable",
    ):
        _SequentialStateUpdate(parent=state, result=state)

    marker = _sealed_node(lambda current: current)(state)
    assert not hasattr(marker, "__dict__")
    assert repr(marker) == "<_SequentialStateUpdate opaque>"
    with pytest.raises((TypeError, pickle.PicklingError)):
        pickle.dumps(marker)
    with pytest.raises(TypeError):
        json.dumps(marker)


def test_reducer_rejects_object_new_and_wrong_snapshot_markers() -> None:
    state = Stage08CollaborationContractFactory.initial_state(_command())
    empty = object.__new__(_SequentialStateUpdate)
    with pytest.raises(
        TypeError,
        match="collaboration_sequential_update_unavailable",
    ):
        _merge_collaboration_state(state, empty)

    wrong_snapshot = object.__new__(_SequentialStateUpdate)
    try:
        object.__setattr__(
            wrong_snapshot,
            "_sealed_snapshot",
            SimpleNamespace(seal=object(), parent=state, result=state),
        )
    except AttributeError:
        object.__setattr__(wrong_snapshot, "parent", state)
        object.__setattr__(wrong_snapshot, "result", state)
    with pytest.raises(
        TypeError,
        match="collaboration_sequential_update_unavailable",
    ):
        _merge_collaboration_state(state, wrong_snapshot)


def test_forged_sequential_marker_cannot_bypass_policy_conflict() -> None:
    analysed = _draft_analysis(
        Stage08CollaborationContractFactory.initial_state(
            _command(action="draft_update")
        ),
        answer="建议一",
    )
    denied = Stage08CollaborationContractFactory.record_policy_result(
        analysed,
        draft_allowed=False,
    )
    allowed = Stage08CollaborationContractFactory.record_policy_result(
        analysed,
        draft_allowed=True,
    )
    forged = object.__new__(_SequentialStateUpdate)
    try:
        object.__setattr__(
            forged,
            "_sealed_snapshot",
            SimpleNamespace(seal=object(), parent=denied, result=allowed),
        )
    except AttributeError:
        object.__setattr__(forged, "parent", denied)
        object.__setattr__(forged, "result", allowed)

    with pytest.raises(
        TypeError,
        match="collaboration_sequential_update_unavailable",
    ):
        _merge_collaboration_state(denied, forged)


def test_e1_modules_have_no_database_tool_network_or_provider_dependencies() -> None:
    root = Path(__file__).resolve().parents[2]
    paths = (
        root / "app/runtime/stage08_collaboration_contracts.py",
        root / "app/agents/stage08_collaboration.py",
    )
    banned_import_roots = {
        "requests",
        "httpx",
        "openai",
        "redis",
        "pymilvus",
        "sqlalchemy",
        "telegram",
    }
    banned_symbols = {
        "OpenRouter",
        "Stage08ToolGateway",
        "Stage06PlatformUnitOfWork",
        "PostgresRetrievalProvider",
    }

    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        assert imported_roots.isdisjoint(banned_import_roots)
        assert banned_symbols.isdisjoint(source.split())
