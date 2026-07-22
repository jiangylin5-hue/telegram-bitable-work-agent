from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Annotated, Any, Final

from langgraph.graph import END, StateGraph

from app.runtime.stage08_collaboration_contracts import (
    Stage08CollaborationContractFactory,
    Stage08CollaborationState,
    _read_outcome_snapshot,
    _state,
    _state_snapshot,
)


Stage08CollaborationNode = Callable[
    [Stage08CollaborationState], Stage08CollaborationState
]

_READ_NODES: Final[tuple[str, ...]] = (
    "read_composite_context",
    "read_retrieval",
    "mark_general_advice",
)
_STATUS_ORDER: Final[dict[str, int]] = {
    "queued": 0,
    "planning": 1,
    "reading": 2,
    "analysing": 3,
    "policy_check": 4,
    "completed": 5,
    "draft_pending": 5,
    "degraded": 5,
    "denied": 5,
    "failed": 5,
    "cancelled": 5,
    "timed_out": 5,
}
_TERMINAL_PRECEDENCE: Final[dict[str, int]] = {
    "cancelled": 6,
    "timed_out": 5,
    "denied": 4,
    "failed": 3,
    "degraded": 3,
    "draft_pending": 2,
    "completed": 1,
}
_SEQUENTIAL_UPDATE_ISSUER: Final[object] = object()
_SEQUENTIAL_UPDATE_SEAL: Final[object] = object()


class _Stage08GraphRoot:
    """LangGraph-only empty root seed; it never reaches an injected node."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<_Stage08GraphRoot private>"


@dataclass(frozen=True, slots=True)
class _SequentialStateUpdateSnapshot:
    seal: object
    parent: Stage08CollaborationState
    result: Stage08CollaborationState


class _SequentialStateUpdate:
    """Process-local anti-misuse marker for one exact node transition."""

    __slots__ = ("_sealed_snapshot",)

    def __new__(
        cls,
        issuer: object = None,
        snapshot: object = None,
        **kwargs: object,
    ):
        del kwargs
        if cls is not _SequentialStateUpdate or issuer is not _SEQUENTIAL_UPDATE_ISSUER:
            raise TypeError("collaboration_sequential_update_unavailable")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_sealed_snapshot", snapshot)
        return instance

    def __init__(
        self,
        issuer: object = None,
        snapshot: object = None,
        **kwargs: object,
    ) -> None:
        del issuer, snapshot, kwargs

    def __getattribute__(self, name: str):
        if name == "__class__":
            return _SequentialStateUpdate
        if name in {"__reduce__", "__reduce_ex__"}:
            return object.__getattribute__(self, name)
        raise AttributeError("collaboration_sequential_update_unavailable")

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("collaboration_sequential_update_unavailable")

    def __repr__(self) -> str:
        return "<_SequentialStateUpdate opaque>"

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("collaboration_sequential_update_unavailable")


@dataclass(frozen=True, slots=True)
class Stage08CollaborationNodes:
    plan_request: Stage08CollaborationNode
    read_composite_context: Stage08CollaborationNode
    read_retrieval: Stage08CollaborationNode
    mark_general_advice: Stage08CollaborationNode
    fan_in: Stage08CollaborationNode
    compress_group_context: Stage08CollaborationNode
    analyse: Stage08CollaborationNode
    policy_gate: Stage08CollaborationNode
    materialize_draft: Stage08CollaborationNode
    finalize: Stage08CollaborationNode

    def __post_init__(self) -> None:
        for name in self.__slots__:
            if not callable(getattr(self, name)):
                raise TypeError("collaboration_node_not_callable")


def build_stage08_collaboration_graph(nodes: Stage08CollaborationNodes) -> Any:
    if type(nodes) is not Stage08CollaborationNodes:
        raise TypeError("collaboration_nodes_invalid")

    # LangGraph 1.0 draws a root schema by calling its value type with no
    # arguments. This private empty seed supports that introspection while every
    # runtime node wrapper below still accepts only the sealed state carrier.
    graph = StateGraph(Annotated[_Stage08GraphRoot, _merge_collaboration_state])
    graph.add_node("plan_request", _sealed_node(nodes.plan_request))
    graph.add_node(
        "read_composite_context",
        _sealed_node(nodes.read_composite_context),
    )
    graph.add_node("read_retrieval", _sealed_node(nodes.read_retrieval))
    graph.add_node(
        "mark_general_advice",
        _sealed_node(nodes.mark_general_advice),
    )
    graph.add_node("fan_in", _sealed_node(nodes.fan_in))
    graph.add_node(
        "compress_group_context",
        _sealed_node(nodes.compress_group_context),
    )
    graph.add_node("analyse", _sealed_node(nodes.analyse))
    graph.add_node("policy_gate", _sealed_node(nodes.policy_gate))
    graph.add_node(
        "materialize_draft",
        _sealed_node(nodes.materialize_draft),
    )
    graph.add_node("finalize", _sealed_node(nodes.finalize))

    graph.set_entry_point("plan_request")
    graph.add_conditional_edges(
        "plan_request",
        _route_after_plan,
        {
            "read_composite_context": "read_composite_context",
            "read_retrieval": "read_retrieval",
            "mark_general_advice": "mark_general_advice",
            "finalize": "finalize",
        },
    )
    graph.add_edge(list(_READ_NODES), "fan_in")
    graph.add_conditional_edges(
        "fan_in",
        _route_or_finalize("compress_group_context"),
        {
            "compress_group_context": "compress_group_context",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges(
        "compress_group_context",
        _route_or_finalize("analyse"),
        {"analyse": "analyse", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "analyse",
        _route_or_finalize("policy_gate"),
        {"policy_gate": "policy_gate", "finalize": "finalize"},
    )
    graph.add_conditional_edges(
        "policy_gate",
        _route_after_policy,
        {
            "materialize_draft": "materialize_draft",
            "finalize": "finalize",
        },
    )
    graph.add_edge("materialize_draft", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=None)


def _sealed_node(node: Stage08CollaborationNode) -> Stage08CollaborationNode:
    def run(state: Stage08CollaborationState) -> object:
        _state_snapshot(state)
        result = node(state)
        _state_snapshot(result)
        return _sequential_state_update(parent=state, result=result)

    return run  # type: ignore[return-value]


def _route_after_plan(state: Stage08CollaborationState) -> list[str] | str:
    if Stage08CollaborationContractFactory.terminal_status(state) is not None:
        return "finalize"
    return list(_READ_NODES)


def _route_or_finalize(next_node: str) -> Callable[[Stage08CollaborationState], str]:
    def route(state: Stage08CollaborationState) -> str:
        if Stage08CollaborationContractFactory.terminal_status(state) is not None:
            return "finalize"
        return next_node

    return route


def _route_after_policy(state: Stage08CollaborationState) -> str:
    if Stage08CollaborationContractFactory.terminal_status(state) is not None:
        return "finalize"
    if Stage08CollaborationContractFactory.policy_allows_draft(state):
        return "materialize_draft"
    return "finalize"


def _merge_collaboration_state(
    left: object,
    right: object,
) -> object:
    # BinaryOperatorAggregate initializes the root with this empty seed. It is
    # never exposed to a node and may only seed the first channel value.
    if type(left) is _Stage08GraphRoot:
        return right
    if type(right) is _Stage08GraphRoot:
        return left
    if type(right) is _SequentialStateUpdate:
        update = _sequential_state_update_snapshot(right)
        if left is update.parent:
            return update.result
        right = update.result
    left_snapshot = _state_snapshot(left)
    right_snapshot = _state_snapshot(right)
    if left_snapshot.command is not right_snapshot.command:
        raise ValueError("collaboration_parallel_command_mismatch")
    if left is right and not left_snapshot.read_outcomes:
        return left

    if left_snapshot.policy_draft_allowed != right_snapshot.policy_draft_allowed:
        raise ValueError("collaboration_parallel_policy_conflict")

    _require_compatible_optional(
        left_snapshot.compressed_digest,
        right_snapshot.compressed_digest,
        error_code="collaboration_parallel_digest_conflict",
    )
    _require_compatible_optional(
        left_snapshot.analysis_decision,
        right_snapshot.analysis_decision,
        error_code="collaboration_parallel_analysis_conflict",
    )
    _require_compatible_optional(
        left_snapshot.safe_view,
        right_snapshot.safe_view,
        error_code="collaboration_parallel_safe_view_conflict",
    )

    left_terminal = left_snapshot.status in _TERMINAL_PRECEDENCE
    right_terminal = right_snapshot.status in _TERMINAL_PRECEDENCE
    if left_terminal or right_terminal:
        if left_snapshot.status != right_snapshot.status:
            raise ValueError("collaboration_parallel_terminal_conflict")
        selected = left_snapshot
    else:
        selected = max(
            (left_snapshot, right_snapshot),
            key=lambda snapshot: _STATUS_ORDER[snapshot.status],
        )
    outcomes: dict[str, object] = {}
    for outcome in (*left_snapshot.read_outcomes, *right_snapshot.read_outcomes):
        branch = _read_outcome_snapshot(outcome).branch
        previous = outcomes.get(branch)
        if previous is not None:
            raise ValueError("collaboration_parallel_read_conflict")
        outcomes[branch] = outcome
    ordered_outcomes = tuple(
        outcomes[branch]
        for branch in ("composite_context", "retrieval", "general_advice")
        if branch in outcomes
    )
    return _state(
        replace(
            selected,
            read_outcomes=ordered_outcomes,
            compressed_digest=(
                right_snapshot.compressed_digest
                if right_snapshot.compressed_digest is not None
                else left_snapshot.compressed_digest
            ),
            analysis_decision=(
                right_snapshot.analysis_decision
                if right_snapshot.analysis_decision is not None
                else left_snapshot.analysis_decision
            ),
            policy_draft_allowed=(
                left_snapshot.policy_draft_allowed
            ),
            degradation_codes=tuple(
                dict.fromkeys(
                    (*left_snapshot.degradation_codes, *right_snapshot.degradation_codes)
                )
            ),
            safe_view=(
                right_snapshot.safe_view
                if right_snapshot.safe_view is not None
                else left_snapshot.safe_view
            ),
        )
    )


def _require_compatible_optional(
    left: object | None,
    right: object | None,
    *,
    error_code: str,
) -> None:
    if left is None or right is None or left is right:
        return
    try:
        compatible = left == right
    except Exception:
        compatible = False
    if compatible is not True:
        raise ValueError(error_code)


def _sequential_state_update(
    *,
    parent: Stage08CollaborationState,
    result: Stage08CollaborationState,
) -> _SequentialStateUpdate:
    _state_snapshot(parent)
    _state_snapshot(result)
    return _SequentialStateUpdate(
        _SEQUENTIAL_UPDATE_ISSUER,
        _SequentialStateUpdateSnapshot(
            seal=_SEQUENTIAL_UPDATE_SEAL,
            parent=parent,
            result=result,
        ),
    )


def _sequential_state_update_snapshot(
    value: object,
) -> _SequentialStateUpdateSnapshot:
    if type(value) is not _SequentialStateUpdate:
        raise TypeError("collaboration_sequential_update_unavailable")
    try:
        snapshot = object.__getattribute__(value, "_sealed_snapshot")
    except (AttributeError, TypeError):
        raise TypeError("collaboration_sequential_update_unavailable") from None
    if (
        type(snapshot) is not _SequentialStateUpdateSnapshot
        or snapshot.seal is not _SEQUENTIAL_UPDATE_SEAL
    ):
        raise TypeError("collaboration_sequential_update_unavailable")
    _state_snapshot(snapshot.parent)
    _state_snapshot(snapshot.result)
    return snapshot


__all__ = [
    "Stage08CollaborationNode",
    "Stage08CollaborationNodes",
    "build_stage08_collaboration_graph",
]
