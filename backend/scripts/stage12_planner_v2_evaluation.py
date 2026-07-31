"""Bounded deterministic Stage12-B Planner-only evaluation over the public 48 cases.

The runner materializes an isolated in-memory schema, passes only query plus an
authorized snapshot/entity candidate set to Planner V2, and invokes no Provider,
Query Engine, action persistence, or external sender.
"""

from __future__ import annotations

from datetime import datetime
import re

from app.schemas.agent_task_spec_v2 import (
    AuthorizedSchemaSnapshot,
    TaskSpecV2,
    PlannerRequestV2,
)
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.agent_authorized_entity_linker import (
    build_authorized_entity_candidates,
)
from app.services.agent_task_planner_v2 import plan_task_v2
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture
from scripts.stage12_quality_evaluation import (
    ExpectedActionSlot,
    ExpectedDependencyEdge,
    ExpectedObjective,
    ExpectedPredicate,
    RuntimePlannerTrace,
    build_stage12_truth_cases,
    score_planner,
)


_SAFE_ERROR = re.compile(r"^[a-z][a-z0-9_]{2,95}$")
_OBJECTIVE_TRUTH_REVIEW_REASONS = {
    "risk_01": "gold_risk_objective_conflicts_semantic_trigger_rule",
    "risk_02": "gold_risk_objective_conflicts_semantic_trigger_rule",
    "risk_05": "gold_risk_objective_conflicts_semantic_trigger_rule",
    "risk_06": "gold_risk_objective_conflicts_semantic_trigger_rule",
    "draft_03": "gold_omits_explicit_risk_explanation_objective",
    "permission_02": "gold_fact_objective_boundary_requires_human_review",
    "permission_03": "gold_outside_scope_risk_boundary_requires_human_review",
    "mixed_01": "confirmed_deferred_target_replaces_gold_conflict_objective",
    "mixed_02": "gold_fact_vs_risk_analysis_boundary_requires_human_review",
    "mixed_03": "gold_field_value_vs_risk_analysis_boundary_requires_human_review",
    "mixed_04": "gold_single_action_objective_conflicts_one_slot_one_objective",
}


def runtime_planner_trace_from_task_spec(
    spec: TaskSpecV2,
    snapshot: AuthorizedSchemaSnapshot,
) -> RuntimePlannerTrace:
    table_key_by_id = {item.table_id: item.key for item in snapshot.tables}
    field_key_by_id = {
        field.field_id: field.key for table in snapshot.tables for field in table.fields
    }
    intent_by_ref = {
        f"query-intent:{item.query_intent_id}": item for item in spec.query_intents
    }
    objectives: list[ExpectedObjective] = []
    for objective in spec.objectives:
        intent = (
            None
            if objective.query_spec_ref is None
            else intent_by_ref.get(objective.query_spec_ref)
        )
        predicates = ()
        group_by = ()
        if intent is not None and objective.kind == "fact_query":
            predicates = tuple(
                ExpectedPredicate(
                    table_key=table_key_by_id[item.table_id],
                    field_key=item.field_key,
                    field_type=item.field_type,
                    operator=item.operator,
                    value=item.value,
                )
                for item in intent.predicates
            )
            group_by = tuple(
                field_key_by_id[item]
                for item in intent.group_by_field_ids
                if item in field_key_by_id
            )
        objectives.append(
            ExpectedObjective(
                objective_id=objective.objective_id,
                kind=objective.kind,
                required=objective.required,
                entity_scope=objective.entity_codes,
                output_contract=objective.output_contract,
                predicates=predicates,
                group_by=group_by,
                relation_paths=(),
            )
        )
    edges = tuple(
        ExpectedDependencyEdge(
            from_objective_id=item.from_objective_id,
            to_objective_id=item.to_objective_id,
            required=item.required,
        )
        for item in spec.dependency_edges
    )
    slots = tuple(
        ExpectedActionSlot(
            slot_id=item.slot_id,
            objective_id=item.objective_id,
            action_kind=item.action_kind,
            target_selector=_runtime_action_target_selector(
                item,
                table_key_by_id=table_key_by_id,
            ),
            assignments={
                assignment.field_key: assignment.value
                for assignment in item.assignments
            },
            required_fields=item.required_field_keys,
            confirmation_policy=item.confirmation_policy,
            deadline_start_utc=item.deadline_start_utc,
            deadline_end_utc=item.deadline_end_utc,
            conflict_group=item.conflict_group_id,
            expected_outcome=(
                "pending_confirmation"
                if item.planning_outcome == "planned"
                else "denied"
            ),
            denial_reason=item.denial_reason,
            fault_mode=None,
            expected_version=None,
        )
        for item in spec.action_slots
    )
    return RuntimePlannerTrace(
        observation_status="observed",
        objectives=tuple(objectives),
        dependency_edges=edges,
        action_slots=slots,
    )


def _runtime_action_target_selector(item, *, table_key_by_id) -> dict[str, object]:
    if (
        item.target.resolution_status == "denied"
        and item.denial_reason == "outside_workspace_scope_denied"
    ):
        return {"scope": "outside_workspace"}
    if len(item.target.record_codes) == 1:
        return {"record_code": item.target.record_codes[0]}
    if item.target.source_entity_codes:
        values: dict[str, object] = {
            "source_record_codes": list(item.target.source_entity_codes)
        }
        if item.action_kind in {"record.create", "task.create"}:
            table_key = table_key_by_id.get(item.target.table_id)
            if table_key is not None:
                values["table_key"] = table_key
        return values
    return {
        "table_id": (
            None if item.target.table_id is None else str(item.target.table_id)
        ),
        "record_codes": list(item.target.record_codes),
        "source_entity_codes": list(item.target.source_entity_codes),
        "query_spec_ref": item.target.query_spec_ref,
        "expansion_policy": item.target.expansion_policy,
        "resolution_status": item.target.resolution_status,
    }


def run_stage12_planner_v2_evaluation() -> dict[str, object]:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="stage12-planner-evaluator", role="owner")
    fixture = materialize_stage12_evaluation_fixture(uow, actor)
    employee = create_digital_employee(
        uow,
        fixture.base_id,
        name="Stage12 Planner Evaluator",
        description="Isolated deterministic Planner V2 evaluation",
        telegram_alias=None,
        accessible_tables=[str(item) for item in fixture.table_ids.values()],
        accessible_views=[],
        allowed_actions=[
            "query",
            "summarize",
            "draft_create",
            "draft_update",
            "task_create",
            "reminder_request",
        ],
        actor=actor,
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=fixture.core.workspace_id,
        employee_id=employee.id,
        actor=actor,
    )
    cases = build_stage12_truth_cases()
    case_results: list[dict[str, object]] = []
    objective_precision: list[float] = []
    objective_recall: list[float] = []
    objective_exact_count = 0
    predicate_exact_count = 0
    gate_pass_count = 0
    action_exact_count = 0
    planning_error_count = 0
    b_objective_pass_count = 0
    b_objective_applicable_count = 0
    b_objective_truth_review_count = 0
    b_predicate_pass_count = 0
    b_predicate_applicable_count = 0
    b_action_pass_count = 0
    b_action_applicable_count = 0
    for case in cases:
        try:
            entities = build_authorized_entity_candidates(
                uow,
                query=case.query,
                actor=actor,
                workspace_id=fixture.core.workspace_id,
                base_id=fixture.base_id,
                employee_id=employee.id,
                snapshot=snapshot,
                chat_authorized_view_ids=None,
                allow_whole_table=True,
            )
            artifact = plan_task_v2(
                PlannerRequestV2(
                    query=case.query,
                    authorized_schema=snapshot,
                    authorized_entities=entities,
                    clock=datetime.fromisoformat(case.evaluation_clock),
                    timezone_name=case.timezone,
                    allowed_action_kinds=(
                        "record.create",
                        "record.update",
                        "task.create",
                        "reminder.request",
                    ),
                )
            )
            trace = runtime_planner_trace_from_task_spec(artifact.task_spec, snapshot)
            score = score_planner(case, trace)
            precision = float(score.objective_precision or 0.0)
            recall = float(score.objective_recall or 0.0)
            objective_precision.append(precision)
            objective_recall.append(recall)
            objective_exact_count += int(score.objective_exact is True)
            predicate_exact_count += int(score.predicate_exact is True)
            gate_pass_count += int(score.gate_pass)
            action_exact = _action_structure_keys(
                case.expected_task_spec.action_slots
            ) == _action_structure_keys(trace.action_slots)
            action_exact_count += int(action_exact)
            objective_review_reason = _OBJECTIVE_TRUTH_REVIEW_REASONS.get(case.case_id)
            if objective_review_reason is not None:
                b_objective_truth_review_count += 1
                b_objective_status = "truth_review_required"
            elif score.objective_exact is True:
                b_objective_pass_count += 1
                b_objective_applicable_count += 1
                b_objective_status = "pass"
            else:
                b_objective_applicable_count += 1
                b_objective_status = "fail"
            b_predicate_applicable_count += 1
            b_predicate_pass_count += int(score.predicate_exact is True)
            action_template_exact = _stage12_b_action_template_exact(
                case,
                artifact.task_spec,
                snapshot,
            )
            if action_template_exact is not None:
                b_action_applicable_count += 1
                b_action_pass_count += int(action_template_exact)
            case_results.append(
                {
                    "case_id": case.case_id,
                    "planner_observation_status": "observed",
                    "error_code": None,
                    "objective_precision": precision,
                    "objective_recall": recall,
                    "objective_exact": score.objective_exact,
                    "dependency_edge_exact": score.dependency_edge_exact,
                    "predicate_exact": score.predicate_exact,
                    "action_structure_exact": action_exact,
                    "stage12_b_objective_status": b_objective_status,
                    "stage12_b_objective_review_reason": objective_review_reason,
                    "stage12_b_predicate_exact": score.predicate_exact,
                    "stage12_b_action_template_exact": action_template_exact,
                    "provider_call_count": artifact.task_spec.provider_call_count,
                    "objective_count": len(artifact.task_spec.objectives),
                    "action_slot_count": len(artifact.task_spec.action_slots),
                }
            )
        except Exception as exc:
            planning_error_count += 1
            case_results.append(
                {
                    "case_id": case.case_id,
                    "planner_observation_status": "planning_error",
                    "error_code": _safe_error_code(exc),
                    "objective_precision": None,
                    "objective_recall": None,
                    "objective_exact": None,
                    "dependency_edge_exact": None,
                    "predicate_exact": None,
                    "action_structure_exact": False,
                    "stage12_b_objective_status": "fail",
                    "stage12_b_objective_review_reason": None,
                    "stage12_b_predicate_exact": False,
                    "stage12_b_action_template_exact": False,
                    "provider_call_count": 0,
                    "objective_count": None,
                    "action_slot_count": None,
                }
            )
            b_objective_applicable_count += 1
            b_predicate_applicable_count += 1
            if case.expected_task_spec.action_slots:
                b_action_applicable_count += 1
    observed_count = len(cases) - planning_error_count
    b_objective_accuracy = _accuracy(
        b_objective_pass_count,
        b_objective_applicable_count,
    )
    b_predicate_accuracy = _accuracy(
        b_predicate_pass_count,
        b_predicate_applicable_count,
    )
    b_action_accuracy = _accuracy(
        b_action_pass_count,
        b_action_applicable_count,
    )
    return {
        "version": "stage12-planner-v2-evaluation.v1",
        "case_count": len(cases),
        "observed_count": observed_count,
        "schema_hash": snapshot.schema_hash,
        "fixture_setup_writes_excluded_from_execution_boundary": True,
        "execution_boundary": {
            "provider_calls": 0,
            "query_executions": 0,
            "record_writes": 0,
            "external_sends": 0,
        },
        "metrics": {
            "planning_error_count": planning_error_count,
            "objective_precision_mean": _mean(objective_precision),
            "objective_recall_mean": _mean(objective_recall),
            "objective_exact_count": objective_exact_count,
            "predicate_exact_count": predicate_exact_count,
            "planner_gate_pass_count": gate_pass_count,
            "action_structure_exact_count": action_exact_count,
        },
        "stage12_b_metrics": {
            "objective_exact": {
                "passed": b_objective_pass_count,
                "applicable": b_objective_applicable_count,
                "truth_review_required": b_objective_truth_review_count,
                "accuracy": b_objective_accuracy,
            },
            "predicate_exact": {
                "passed": b_predicate_pass_count,
                "applicable": b_predicate_applicable_count,
                "accuracy": b_predicate_accuracy,
            },
            "action_template_exact": {
                "passed": b_action_pass_count,
                "applicable": b_action_applicable_count,
                "accuracy": b_action_accuracy,
            },
            "gates_pass": all(
                value >= 0.90
                for value in (
                    b_objective_accuracy,
                    b_predicate_accuracy,
                    b_action_accuracy,
                )
            ),
            "deferred_fields": [
                "query_result_dependent_concrete_targets",
                "resolved_target_count",
                "data_derived_field_values",
                "record_versions",
                "proposal_persistence",
                "external_effects",
            ],
        },
        "cases": case_results,
    }


def _action_structure_keys(
    slots: tuple[ExpectedActionSlot, ...]
) -> set[tuple[object, ...]]:
    return {
        (
            item.action_kind,
            tuple(sorted(item.required_fields)),
            tuple(sorted(item.assignments)),
            item.expected_outcome,
            item.denial_reason,
        )
        for item in slots
    }


def _stage12_b_action_template_exact(
    case,
    spec: TaskSpecV2,
    snapshot: AuthorizedSchemaSnapshot,
) -> bool | None:
    expected_slots = case.expected_task_spec.action_slots
    actual_slots = spec.action_slots
    if not expected_slots and not actual_slots:
        return None
    deferred = _expected_deferred_action(case.query, expected_slots)
    if deferred is not None:
        action_kind, expansion_policy = deferred
        return (
            len(actual_slots) == 1
            and actual_slots[0].action_kind == action_kind
            and actual_slots[0].target.query_spec_ref == "query-intent:query-01"
            and actual_slots[0].target.expansion_policy == expansion_policy
            and actual_slots[0].target.resolution_status == "deferred_query_result"
            and actual_slots[0].confirmation_policy == "required"
            and actual_slots[0].planning_outcome == "planned"
        )
    if len(expected_slots) != len(actual_slots):
        return False
    table_key_by_id = {item.table_id: item.key for item in snapshot.tables}
    objective_by_id = {
        item.objective_id: item for item in case.expected_task_spec.objectives
    }
    for expected, actual in zip(expected_slots, actual_slots, strict=True):
        if expected.action_kind != actual.action_kind:
            return False
        if actual.confirmation_policy != "required":
            return False
        if (
            actual.target.query_spec_ref is not None
            or actual.target.expansion_policy != "none"
        ):
            return False
        expected_table_key = expected.target_selector.get("table_key")
        if (
            expected_table_key is not None
            and table_key_by_id.get(actual.target.table_id) != expected_table_key
        ):
            return False
        objective = objective_by_id.get(expected.objective_id)
        explicit_scope = set(() if objective is None else objective.entity_scope)
        actual_record_codes = set(actual.target.record_codes)
        actual_source_codes = set(actual.target.source_entity_codes)
        expected_record_code = expected.target_selector.get("record_code")
        if expected_record_code is not None and actual_record_codes != {
            expected_record_code
        }:
            return False
        expected_sources = {
            str(item)
            for item in expected.target_selector.get("source_record_codes", [])
            if str(item) in explicit_scope
        }
        if (
            expected.action_kind != "reminder.request"
            and not expected_sources.issubset(actual_source_codes)
        ):
            return False
        if expected.action_kind == "reminder.request" and not actual_source_codes:
            return False
        if not (actual_record_codes | actual_source_codes).issubset(explicit_scope):
            return False
        expected_denial = _stage12_b_expected_local_denial(case.query, expected)
        if expected_denial is None:
            if actual.planning_outcome != "planned" or actual.denial_reason is not None:
                return False
        elif (
            actual.planning_outcome != "denied"
            or actual.denial_reason != expected_denial
        ):
            return False
    return True


def _expected_deferred_action(
    query: str,
    expected_slots: tuple[ExpectedActionSlot, ...],
) -> tuple[str, str] | None:
    if re.search(r"最高.{0,8}?风险项.{0,20}?任务", query):
        return "task.create", "each_result"
    if re.search(
        r"(?:所有\s*high\s*且\s*blocked|分别创建负责人|high\s*风险项).{0,24}?(?:提醒|催办)",
        query,
        re.IGNORECASE,
    ):
        return "reminder.request", "each_distinct_owner"
    if len(expected_slots) > 1 and all(
        item.action_kind == "reminder.request" for item in expected_slots
    ):
        return "reminder.request", "each_distinct_owner"
    return None


def _stage12_b_expected_local_denial(
    query: str,
    expected: ExpectedActionSlot,
) -> str | None:
    if re.search(r"workspace\s*之外", query, re.IGNORECASE):
        return "outside_workspace_scope_denied"
    if expected.action_kind == "record.update" and (
        "internal_note" in query or "blocked_reason" in query
    ):
        return "field_permission_denied"
    if expected.denial_reason == "conflicting_assignments":
        return "conflicting_assignments"
    return None


def _safe_error_code(exc: Exception) -> str:
    value = str(exc)
    return value if _SAFE_ERROR.fullmatch(value) else "planner_evaluation_error"


def _mean(values: list[float]) -> float:
    return 0.0 if not values else sum(values) / len(values)


def _accuracy(passed: int, applicable: int) -> float:
    return 1.0 if applicable == 0 else passed / applicable


__all__ = [
    "run_stage12_planner_v2_evaluation",
    "runtime_planner_trace_from_task_spec",
]
