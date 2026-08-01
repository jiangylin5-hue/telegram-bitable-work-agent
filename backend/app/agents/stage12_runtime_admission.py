"""Bounded LangGraph used only for Stage12 admission work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypedDict

from langgraph.graph import END, StateGraph

from app.schemas.agent_stage12_runtime import Stage12RuntimeAdmissionRequest


class Stage12AdmissionState(TypedDict, total=False):
    request: Stage12RuntimeAdmissionRequest
    completed_nodes: tuple[str, ...]
    context: object
    schema_snapshot: object
    task_artifact: object
    query_artifacts: tuple[object, ...]
    admission_result: object
    run: object
    replayed: bool
    schema_artifact: object
    idempotency_record: object


AdmissionNode = Callable[[Stage12AdmissionState], dict[str, object]]


@dataclass(frozen=True, slots=True)
class Stage12AdmissionDependencies:
    authorize_schema: AdmissionNode
    plan_task: AdmissionNode
    execute_authorized_inputs: AdmissionNode
    persist_typed_inputs: AdmissionNode
    dispatch_commands: AdmissionNode


def build_stage12_admission_graph(dependencies: Stage12AdmissionDependencies):
    graph = StateGraph(Stage12AdmissionState)
    graph.add_node("authorize_schema", dependencies.authorize_schema)
    graph.add_node("plan_task", dependencies.plan_task)
    graph.add_node(
        "execute_authorized_inputs",
        dependencies.execute_authorized_inputs,
    )
    graph.add_node("persist_typed_inputs", dependencies.persist_typed_inputs)
    graph.add_node("dispatch_commands", dependencies.dispatch_commands)
    graph.set_entry_point("authorize_schema")
    graph.add_edge("authorize_schema", "plan_task")
    graph.add_edge("plan_task", "execute_authorized_inputs")
    graph.add_edge("execute_authorized_inputs", "persist_typed_inputs")
    graph.add_edge("persist_typed_inputs", "dispatch_commands")
    graph.add_edge("dispatch_commands", END)
    return graph.compile()


__all__ = [
    "Stage12AdmissionDependencies",
    "Stage12AdmissionState",
    "build_stage12_admission_graph",
]
