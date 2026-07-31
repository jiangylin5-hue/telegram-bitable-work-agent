"""Bounded deterministic Stage12-C Query/Join/Aggregate diagnostic."""

from __future__ import annotations

from datetime import datetime
import json
import re
from uuid import UUID

from app.schemas.agent_task_spec_v2 import PlannerRequestV2
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.agent_authorized_entity_linker import (
    build_authorized_entity_candidates,
)
from app.services.agent_task_planner_v2 import plan_task_v2
from app.services.authorized_query_compiler import compile_authorized_query_plan
from app.services.authorized_table_query import execute_authorized_query
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture
from scripts.stage12_quality_evaluation import build_stage12_truth_cases


_SAFE_ERROR = re.compile(r"^[a-z][a-z0-9_]{2,95}$")


def run_stage12_query_engine_evaluation(
    *,
    case_ids: tuple[str, ...] | None = None,
) -> dict[str, object]:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="stage12-query-evaluator", role="owner")
    fixture = materialize_stage12_evaluation_fixture(uow, actor)
    employee = create_digital_employee(
        uow,
        fixture.base_id,
        name="Stage12 Query Evaluator",
        description="Bounded deterministic C diagnostic",
        telegram_alias=None,
        accessible_tables=[str(item) for item in fixture.table_ids.values()],
        accessible_views=[],
        allowed_actions=["query", "summarize"],
        actor=actor,
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=fixture.core.workspace_id,
        employee_id=employee.id,
        actor=actor,
    )
    relations = build_authorized_relation_catalog(uow, snapshot)
    all_cases = build_stage12_truth_cases()
    selected = tuple(
        case for case in all_cases if case_ids is None or case.case_id in set(case_ids)
    )
    code_by_record_id = _record_code_map(uow, fixture.table_ids)
    relation_name_by_field_id = _relation_name_map(snapshot)
    field_identity_by_id = _field_identity_map(snapshot)
    rows: list[dict[str, object]] = []
    applicable = 0
    exact = 0
    aggregate_applicable = 0
    aggregate_exact_count = 0
    sort_applicable = 0
    sort_exact_count = 0
    safety_passed = 0
    for case in selected:
        runtime_status = "not_applicable"
        error_code = None
        actual_codes: set[str] = set()
        actual_relation_paths: set[tuple[str, ...]] = set()
        actual_aggregates: set[tuple[str, str, str | None, str, str]] = set()
        actual_sorts: set[tuple[str, str, str, str, tuple[str, ...], bool]] = set()
        result_hashes: list[str] = []
        source_versions_seen = False
        source_versions_valid = True
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
            task_artifact = plan_task_v2(
                PlannerRequestV2(
                    query=case.query,
                    authorized_schema=snapshot,
                    authorized_entities=entities,
                    clock=datetime.fromisoformat(case.evaluation_clock),
                    timezone_name=case.timezone,
                    allowed_action_kinds=(),
                )
            )
            if task_artifact.task_spec.query_intents:
                runtime_status = "executed"
                for intent in task_artifact.task_spec.query_intents:
                    plan = compile_authorized_query_plan(
                        task_spec=task_artifact.task_spec,
                        query_intent_id=intent.query_intent_id,
                        snapshot=snapshot,
                        relations=relations,
                        authorized_view_ids=(),
                    )
                    artifact = execute_authorized_query(
                        uow,
                        actor=actor,
                        workspace_id=fixture.core.workspace_id,
                        employee_id=employee.id,
                        chat_view_ids=None,
                        snapshot=snapshot,
                        plan=plan,
                        allow_whole_table=True,
                    )
                    result_hashes.append(artifact.result.result_hash)
                    actual_aggregates.update(
                        _artifact_aggregates(artifact, field_identity_by_id)
                    )
                    actual_sorts.update(_artifact_sorts(artifact, field_identity_by_id))
                    actual_codes.update(
                        code_by_record_id[item.record_id]
                        for item in artifact.result.records
                        if item.record_id in code_by_record_id
                    )
                    actual_codes.update(
                        code_by_record_id[item.record_id]
                        for item in artifact.result.source_versions
                        if item.record_id in code_by_record_id
                    )
                    source_versions_seen = source_versions_seen or bool(
                        artifact.result.source_versions
                    )
                    source_versions_valid = source_versions_valid and all(
                        item.record_version >= 1
                        for item in artifact.result.source_versions
                    )
                    actual_relation_paths.update(
                        _semantic_artifact_relation_paths(
                            artifact,
                            task_spec=task_artifact.task_spec,
                            relation_names=relation_name_by_field_id,
                            snapshot=snapshot,
                        )
                    )
        except Exception as exc:
            runtime_status = "refused"
            error_code = _safe_error_code(exc)

        # Gold is intentionally read only after planning/compile/execution/refusal.
        expected = _read_expected_query_result(case)
        case_applicable = _is_c_applicable(expected)
        applicable += int(case_applicable)
        required = set(expected.required_result_records)
        allowed = set(expected.allowed_evidence_records)
        forbidden = set(expected.forbidden_result_records)
        expected_paths = set(expected.relation_paths)
        expected_aggregates = _expected_aggregates(expected)
        expected_sorts = _expected_sorts(expected)
        result_exact = (
            runtime_status == "executed"
            and required.issubset(actual_codes)
            and actual_codes.issubset(required | allowed)
            and not (actual_codes & forbidden)
        )
        relation_exact = runtime_status == "executed" and _relation_paths_exact(
            expected_paths,
            actual_relation_paths,
        )
        aggregate_exact = (
            runtime_status == "executed" and expected_aggregates == actual_aggregates
        )
        sort_exact = runtime_status == "executed" and expected_sorts == actual_sorts
        has_valid_versions = source_versions_seen and source_versions_valid
        permission_safe = not (actual_codes & forbidden)
        case_exact = (
            (
                result_exact
                and relation_exact
                and aggregate_exact
                and sort_exact
                and has_valid_versions
                and permission_safe
            )
            if case_applicable
            else None
        )
        exact += int(case_exact is True)
        aggregate_is_applicable = bool(expected.aggregates)
        aggregate_applicable += int(aggregate_is_applicable)
        aggregate_exact_count += int(aggregate_is_applicable and aggregate_exact)
        sort_is_applicable = bool(expected.sort_specs)
        sort_applicable += int(sort_is_applicable)
        sort_exact_count += int(sort_is_applicable and sort_exact)
        safety_passed += int(permission_safe)
        rows.append(
            {
                "case_id": case.case_id,
                "applicable": case_applicable,
                "status": runtime_status,
                "error_code": error_code,
                "result_exact": result_exact,
                "relation_exact": relation_exact,
                "aggregate_exact": aggregate_exact,
                "sort_exact": sort_exact,
                "source_versions_valid": has_valid_versions,
                "permission_safe": permission_safe,
                "case_exact": case_exact,
                "result_hashes": result_hashes,
                "actual_record_codes": sorted(actual_codes),
                "expected_record_codes": sorted(required),
                "allowed_evidence_codes": sorted(allowed),
                "actual_relation_paths": sorted(actual_relation_paths),
                "expected_relation_paths": sorted(expected_paths),
                "actual_aggregates": sorted(actual_aggregates),
                "expected_aggregates": sorted(expected_aggregates),
                "actual_sorts": sorted(actual_sorts),
                "expected_sorts": sorted(expected_sorts),
            }
        )
    return {
        "version": "stage12-query-engine-evaluation.v1",
        "raw_case_count": len(selected),
        "applicable_case_count": applicable,
        "exact_case_count": exact,
        "aggregate_applicable_case_count": aggregate_applicable,
        "aggregate_exact_case_count": aggregate_exact_count,
        "sort_applicable_case_count": sort_applicable,
        "sort_exact_case_count": sort_exact_count,
        "safety_pass_count": safety_passed,
        "exact_accuracy": 1.0 if applicable == 0 else exact / applicable,
        "scope_hash": snapshot.scope_hash,
        "schema_hash": snapshot.schema_hash,
        "execution_boundary": {
            "provider_calls": 0,
            "action_expansions": 0,
            "record_writes_after_fixture_setup": 0,
            "external_sends": 0,
        },
        "cases": rows,
    }


def _read_expected_query_result(case):
    return case.expected_query_result


def _is_c_applicable(expected) -> bool:
    return bool(
        expected.required_result_records
        or expected.allowed_evidence_records
        or expected.forbidden_result_records
        or expected.aggregates
        or expected.relation_paths
        or expected.sort_specs
    )


def _record_code_map(uow, table_ids: dict[str, UUID]) -> dict[UUID, str]:
    identity_fields = {
        "projects": "project_code",
        "work_items": "ticket_code",
        "risks": "risk_code",
        "owners": "owner_code",
        "daily_metrics": "date",
        "interactions": "interaction_code",
    }
    values: dict[UUID, str] = {}
    for table_key, field_key in identity_fields.items():
        for record in uow.list_records(table_ids[table_key]):
            raw = str(record.values[field_key])
            values[record.id] = f"DAILY-{raw}" if table_key == "daily_metrics" else raw
    return values


def _relation_name_map(snapshot) -> dict[UUID, str]:
    return {
        field.field_id: f"{table.key}.{field.key}"
        for table in snapshot.tables
        for field in table.fields
        if field.field_type == "linked_record"
    }


def _field_identity_map(snapshot) -> dict[UUID, tuple[str, str, tuple[str, ...]]]:
    return {
        field.field_id: (table.key, field.key, tuple(field.choices))
        for table in snapshot.tables
        for field in table.fields
    }


def _artifact_relation_paths(plan, names: dict[UUID, str]) -> set[tuple[str, ...]]:
    chains = (
        tuple(path.steps for path in plan.traversal_paths)
        if plan.traversal_paths
        else (() if not plan.traversals else (plan.traversals,))
    )
    return {
        tuple(names[item.link_field_id] for item in chain) for chain in chains if chain
    }


def _semantic_artifact_relation_paths(
    artifact,
    *,
    task_spec,
    relation_names: dict[UUID, str],
    snapshot,
    result_record_ids: set[UUID] | None = None,
) -> set[tuple[str, ...]]:
    if not artifact.plan.traversal_paths:
        return _artifact_relation_paths(artifact.plan, relation_names)
    semantic_intent = next(
        (
            intent
            for intent in task_spec.query_intents
            if intent.query_intent_id == artifact.plan.query_intent_id
        ),
        None,
    )
    optional_context_table_ids = (
        set()
        if semantic_intent is None
        else {
            join.target_table_id
            for join in semantic_intent.execution_spec.join_intents
            if join.requirement == "optional"
        }
    )
    if result_record_ids is None:
        result_table_ids = {
            item.table_id
            for item in artifact.result.records
            if item.table_id not in optional_context_table_ids
        }
    else:
        source_tables = {
            item.record_id: item.table_id for item in artifact.result.source_versions
        }
        result_table_ids = {
            source_tables[record_id]
            for record_id in result_record_ids
            if record_id in source_tables
        }
    table_keys = {item.table_id: item.key for item in snapshot.tables}
    field_tables = {
        field.field_id: table.table_id
        for table in snapshot.tables
        for field in table.fields
    }
    projected_table_ids = {
        field_tables[field_id]
        for field_id in artifact.plan.projection_field_ids
        if field_id in field_tables
    }
    query_ref = f"query-intent:{artifact.plan.query_intent_id}"
    owner_expansion = any(
        slot.target.query_spec_ref == query_ref
        and slot.target.expansion_policy == "each_distinct_owner"
        for slot in task_spec.action_slots
    )
    values: set[tuple[str, ...]] = set()
    for path in artifact.plan.traversal_paths:
        optional_evidence_only = (
            path.join_mode == "left"
            and path.target_table_id not in result_table_ids
            and table_keys.get(path.target_table_id) == "risks"
            and path.target_table_id in projected_table_ids
            and owner_expansion
        )
        if optional_evidence_only:
            continue
        values.add(tuple(relation_names[item.link_field_id] for item in path.steps))
    return values


def _relation_paths_exact(
    expected: set[tuple[str, ...]],
    actual: set[tuple[str, ...]],
) -> bool:
    return expected.issubset(actual) and all(
        any(path == candidate[: len(path)] for candidate in expected) for path in actual
    )


def _artifact_aggregates(
    artifact,
    fields: dict[UUID, tuple[str, str, tuple[str, ...]]],
) -> set[tuple[str, str, str | None, str, str]]:
    specs = {item.aggregate_id: item for item in artifact.plan.aggregates}
    values: set[tuple[str, str, str | None, str, str]] = set()
    for aggregate in artifact.result.aggregates:
        spec = specs[aggregate.aggregate_id]
        field_key = None if spec.field_id is None else fields[spec.field_id][1]
        group_key = _scalar_group_key(aggregate.group_key)
        if group_key is None and len(artifact.plan.entity_codes) == 1:
            group_key = artifact.plan.entity_codes[0]
        values.add(
            (
                spec.output_key,
                spec.function,
                field_key,
                _canonical_value(group_key),
                _canonical_value(aggregate.value),
            )
        )
    return values


def _expected_aggregates(expected) -> set[tuple[str, str, str | None, str, str]]:
    return {
        (
            item.name,
            item.function,
            item.field_key,
            _canonical_value(item.group_key),
            _canonical_value(item.value),
        )
        for item in expected.aggregates
    }


def _artifact_sorts(
    artifact,
    fields: dict[UUID, tuple[str, str, tuple[str, ...]]],
) -> set[tuple[str, str, str, str, tuple[str, ...], bool]]:
    values: set[tuple[str, str, str, str, tuple[str, ...], bool]] = set()
    for index, sort in enumerate(artifact.plan.sort_rules):
        if sort.field_id is None:
            continue
        table_key, field_key, options = fields[sort.field_id]
        values.add(
            (
                table_key,
                field_key,
                sort.direction,
                sort.nulls,
                options if sort.mode == "field_order" else (),
                index > 0,
            )
        )
    return values


def _expected_sorts(expected) -> set[tuple[str, str, str, str, tuple[str, ...], bool]]:
    return {
        (
            item.table_key,
            item.field_key,
            item.direction,
            item.nulls,
            tuple(item.value_order),
            item.tie_breaker,
        )
        for item in expected.sort_specs
    }


def _scalar_group_key(value):
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    if isinstance(value, dict) and isinstance(value.get("label"), str):
        return value["label"]
    return value


def _canonical_value(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_error_code(exc: Exception) -> str:
    candidate = getattr(exc, "code", None)
    if not isinstance(candidate, str):
        candidate = str(exc)
    return candidate if _SAFE_ERROR.fullmatch(candidate) else "query_evaluation_error"


if __name__ == "__main__":
    print(
        json.dumps(run_stage12_query_engine_evaluation(), ensure_ascii=False, indent=2)
    )


__all__ = ["run_stage12_query_engine_evaluation"]
