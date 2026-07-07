from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.stage05_state import Stage05WorkflowState


Stage05SupervisorNode = Callable[[Stage05WorkflowState], Stage05WorkflowState]


@dataclass(frozen=True)
class Stage05SupervisorNodeSet:
    mark_running: Stage05SupervisorNode
    route_message: Stage05SupervisorNode
    apply_policy: Stage05SupervisorNode
    finalize_message: Stage05SupervisorNode


def build_stage05_supervisor_graph(nodes: Stage05SupervisorNodeSet) -> Any:
    graph = StateGraph(Stage05WorkflowState)
    graph.add_node("mark_running", nodes.mark_running)
    graph.add_node("route_message", nodes.route_message)
    graph.add_node("apply_policy", nodes.apply_policy)
    graph.add_node("finalize_message", nodes.finalize_message)

    graph.set_entry_point("mark_running")
    graph.add_edge("mark_running", "route_message")
    graph.add_edge("route_message", "apply_policy")
    graph.add_edge("apply_policy", "finalize_message")
    graph.add_edge("finalize_message", END)
    return graph.compile()


__all__ = [
    "Stage05SupervisorNode",
    "Stage05SupervisorNodeSet",
    "build_stage05_supervisor_graph",
]
