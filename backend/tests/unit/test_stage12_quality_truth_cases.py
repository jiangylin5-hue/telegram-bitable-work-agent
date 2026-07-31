from __future__ import annotations

from collections import Counter
from dataclasses import asdict

import pytest

from scripts.stage09_multitable_chinese_eval import (
    _PROJECT_ROWS,
    _RISK_ROWS,
    _WORK_ITEM_ROWS,
)
from scripts.stage11_complex_coordination_eval import build_complex_cases
from scripts.stage12_quality_evaluation import (
    DEFAULT_GOLD_AUDIT_PATH,
    DEFAULT_TRUTH_PATH,
    build_stage12_truth_cases,
    canonical_sha256,
    case_payload_for_hash,
    generate_stage12_truth_files,
    load_gold_audit_report,
    load_truth_cases,
    validate_truth_set,
    validate_truth_against_fixture,
    _fixture_snapshot,
    audit_truth_set,
)


def test_v2_truth_set_has_all_48_unique_chinese_cases_and_legacy_distribution() -> None:
    cases = build_stage12_truth_cases()

    assert len(cases) == 48
    assert len({item.case_id for item in cases}) == 48
    assert len({item.query for item in cases}) == 48
    assert all(
        any("\u3400" <= char <= "\u9fff" for char in item.query) for item in cases
    )
    assert Counter(item.category for item in cases) == {
        "multi_table": 8,
        "risk": 6,
        "daily_summary": 6,
        "record_draft": 6,
        "task_create": 4,
        "reminder": 4,
        "permission": 4,
        "fault": 2,
        "multi_intent": 8,
    }
    validate_truth_set(cases)


def test_truth_files_are_literal_strict_round_trip_inputs() -> None:
    from_default = build_stage12_truth_cases()
    from_path = load_truth_cases(DEFAULT_TRUTH_PATH)
    audit = load_gold_audit_report(DEFAULT_GOLD_AUDIT_PATH)

    assert from_default == from_path
    assert audit.version == "gold-audit-report.v2"
    assert audit.truth_case_count == 48
    assert len(audit.entries) == 48
    assert {entry.case_id for entry in audit.entries} == {
        case.case_id for case in from_default
    }


def test_generator_reproduces_checked_in_truth_and_audit_files(tmp_path) -> None:
    truth_path = tmp_path / "truth.json"
    audit_path = tmp_path / "truth.audit.json"

    generate_stage12_truth_files(truth_path=truth_path, audit_path=audit_path)

    assert truth_path.read_bytes() == DEFAULT_TRUTH_PATH.read_bytes()
    assert audit_path.read_bytes() == DEFAULT_GOLD_AUDIT_PATH.read_bytes()


def test_objectives_actions_and_edges_use_v2_canonical_names() -> None:
    cases = build_stage12_truth_cases()
    legacy_objective_names = {
        "fact",
        "risk",
        "task",
        "reminder",
        "restricted_data",
        "conflict",
    }
    canonical_action_kinds = {
        "record.create",
        "record.update",
        "task.create",
        "reminder.request",
    }

    assert all(
        objective.kind not in legacy_objective_names
        for case in cases
        for objective in case.expected_task_spec.objectives
    )
    assert all(
        slot.action_kind in canonical_action_kinds
        for case in cases
        for slot in case.expected_task_spec.action_slots
    )
    assert all(
        edge.from_objective_id != edge.to_objective_id
        for case in cases
        for edge in case.expected_task_spec.dependency_edges
    )


def test_risk_02_corrects_legacy_gold_from_mt_008_to_mt_017() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}

    assert by_id["risk_02"].expected_query_result.required_result_records == ("MT-017",)
    assert "MT-008" in by_id["risk_02"].expected_query_result.forbidden_result_records
    assert by_id["risk_02"].gold_audit.change_reason == (
        "corrected_legacy_gold_mt_008_to_mt_017"
    )
    assert by_id["risk_02"].expected_task_spec.objectives[0].entity_scope == ()


def test_explicit_multi_entity_scope_does_not_use_invalid_text_in_predicate() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}
    objective = by_id["risk_03"].expected_task_spec.objectives[0]

    assert objective.entity_scope == ("PRJ-ATLAS", "PRJ-BEACON")
    assert all(
        not (predicate.field_type == "text" and predicate.operator == "in")
        for predicate in objective.predicates
    )


def test_entity_scope_contains_query_entities_not_expected_result_records() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}
    expected_non_empty = {
        "join_01": ("PRJ-ATLAS",),
        "join_02": ("PRJ-BEACON",),
        "join_03": ("RISK-001", "RISK-002", "RISK-004"),
        "join_04": ("PRJ-EMBER",),
        "join_05": ("PRJ-FJORD",),
        "risk_03": ("PRJ-ATLAS", "PRJ-BEACON"),
        "daily_02": ("PRJ-ATLAS", "PRJ-BEACON"),
        "draft_01": ("MT-014",),
        "draft_02": ("MT-012",),
        "draft_03": ("MT-017",),
        "draft_04": ("PRJ-ATLAS",),
        "draft_05": ("PRJ-BEACON",),
        "draft_06": ("PRJ-FJORD",),
        "task_01": ("PRJ-ATLAS",),
        "task_02": ("MT-004",),
        "task_03": ("PRJ-EMBER",),
        "task_04": ("PRJ-FJORD", "MT-017"),
        "reminder_01": ("MT-001",),
        "reminder_02": ("PRJ-BEACON", "MT-004"),
        "reminder_04": ("PRJ-FJORD", "MT-017"),
        "permission_02": ("MT-001",),
        "fault_01": ("PRJ-ATLAS",),
        "fault_02": ("MT-014",),
        "mixed_02": ("MT-014",),
        "mixed_04": ("PRJ-ATLAS", "PRJ-BEACON"),
        "mixed_06": ("MT-012",),
        "mixed_08": ("MT-017",),
    }

    for case_id, case in by_id.items():
        expected = expected_non_empty.get(case_id, ())
        assert all(
            objective.entity_scope == expected
            for objective in case.expected_task_spec.objectives
        ), case_id


def test_mixed_08_preserves_conflicted_update_and_independent_task_slot() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}
    mixed = by_id["mixed_08"]
    slots = mixed.expected_task_spec.action_slots

    assert len(slots) == 2
    assert slots[0].action_kind == "record.update"
    assert slots[0].expected_outcome == "denied"
    assert slots[0].conflict_group == "status-conflict"
    assert slots[1].action_kind == "task.create"
    assert slots[1].expected_outcome == "pending_confirmation"
    assert slots[1].assignments["due_date"] == "2026-07-30"


def test_aggregate_truth_uses_typed_fixture_values() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}

    join_08 = {
        item.group_key: item.value
        for item in by_id["join_08"].expected_query_result.aggregates
    }
    assert join_08 == {
        "PRJ-ATLAS": 3,
        "PRJ-BEACON": 2,
        "PRJ-CEDAR": 1,
        "PRJ-DELTA": 3,
        "PRJ-EMBER": 2,
        "PRJ-FJORD": 2,
    }

    risk_06 = {
        item.group_key: item.value
        for item in by_id["risk_06"].expected_query_result.aggregates
    }
    assert risk_06 == {"high": 3, "medium": 3}

    daily_01 = {
        item.name: item.value
        for item in by_id["daily_01"].expected_query_result.aggregates
    }
    assert daily_01 == {"completed": 5, "in_progress": 4, "blocked": 4}


def test_predicate_field_types_match_imported_fixture_schema() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}
    expected_types = {
        ("work_items", "risk_level"): "single_select",
        ("projects", "phase"): "text",
        ("projects", "delivery_state"): "text",
        ("risks", "level"): "single_select",
        ("work_items", "priority"): "single_select",
        ("work_items", "status"): "status",
        ("risks", "status"): "status",
    }

    for case in by_id.values():
        for objective in case.expected_task_spec.objectives:
            for predicate in objective.predicates:
                expected = expected_types.get(
                    (predicate.table_key, predicate.field_key)
                )
                if expected is not None:
                    assert predicate.field_type == expected, case.case_id


def test_daily_05_lists_only_requested_delivery_statuses() -> None:
    case = next(
        item for item in build_stage12_truth_cases() if item.case_id == "daily_05"
    )
    result = case.expected_query_result
    fact = case.expected_task_spec.objectives[0]

    assert set(result.required_result_records) == {
        "PRJ-ATLAS",
        "PRJ-BEACON",
        "PRJ-FJORD",
        "MT-002",
        "MT-003",
        "MT-005",
        "MT-006",
        "MT-016",
        "MT-017",
        "MT-018",
    }
    assert {"MT-001", "MT-004"} <= set(result.forbidden_result_records)
    assert any(
        predicate.table_key == "work_items"
        and predicate.field_key == "status"
        and predicate.operator == "in"
        and predicate.value == ["in_progress", "planned", "done"]
        for predicate in fact.predicates
    )


def test_join_08_separates_unfinished_aggregate_from_all_risk_listing() -> None:
    case = next(
        item for item in build_stage12_truth_cases() if item.case_id == "join_08"
    )
    fact_objectives = tuple(
        objective
        for objective in case.expected_task_spec.objectives
        if objective.kind == "fact_query"
    )

    assert len(fact_objectives) == 2
    unfinished = next(item for item in fact_objectives if item.predicates)
    all_risks = next(item for item in fact_objectives if not item.predicates)
    assert unfinished.output_contract == "unfinished_work_item_aggregates"
    assert unfinished.relation_paths == (("work_items.project_link",),)
    assert all_risks.output_contract == "project_risk_codes"
    assert all_risks.relation_paths == (
        ("risks.affected_work_items", "work_items.project_link"),
    )


def test_sort_requirements_include_semantic_order_and_stable_tie_breaker() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}

    for case_id, field_key in (("daily_04", "priority"), ("mixed_01", "risk_level")):
        specs = by_id[case_id].expected_query_result.sort_specs
        assert specs[0].field_key == field_key
        assert specs[0].value_order == ("high", "medium", "low")
        assert specs[1].field_key == "ticket_code"
        assert specs[1].direction == "asc"
        assert specs[1].tie_breaker is True


def test_multi_action_truth_preserves_all_independent_slots_and_conflict_dag() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}
    mixed_03 = by_id["mixed_03"].expected_task_spec
    mixed_06 = by_id["mixed_06"].expected_task_spec
    mixed_08 = by_id["mixed_08"].expected_task_spec

    assert len(mixed_03.action_slots) == 5
    assert {
        slot.target_selector["source_record_codes"][0] for slot in mixed_03.action_slots
    } == {"MT-001", "MT-004", "MT-012", "MT-014", "MT-017"}
    assert mixed_06.action_slots[0].expected_outcome == "denied"
    assert mixed_06.action_slots[1].expected_outcome == "pending_confirmation"
    assert "risk_analysis" not in {objective.kind for objective in mixed_08.objectives}
    conflict_id = next(
        objective.objective_id
        for objective in mixed_08.objectives
        if objective.kind == "conflict_resolution"
    )
    update_id = mixed_08.action_slots[0].objective_id
    assert any(
        edge.from_objective_id == conflict_id and edge.to_objective_id == update_id
        for edge in mixed_08.dependency_edges
    )
    assert mixed_06.action_slots[0].denial_reason == "field_permission_denied"
    assert mixed_08.action_slots[0].denial_reason == "conflicting_assignments"
    assert by_id["mixed_01"].expected_task_spec.action_slots[0].denial_reason == (
        "ambiguous_highest_risk_target"
    )
    fault_slot = by_id["fault_02"].expected_task_spec.action_slots[0]
    assert fault_slot.denial_reason == "record_version_conflict"
    assert fault_slot.expected_version == 1
    assert fault_slot.fault_mode == "record_version_drift"


def test_date_aware_actions_use_production_deadlines_without_synthetic_reminder_value() -> (
    None
):
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}

    task_today = by_id["task_02"].expected_task_spec.action_slots[0]
    reminder_today = by_id["reminder_01"].expected_task_spec.action_slots[0]
    mixed_deadline = by_id["mixed_08"].expected_task_spec.action_slots[1]

    assert task_today.deadline_start_utc.isoformat() == "2026-07-28T16:00:00+00:00"
    assert task_today.deadline_end_utc.isoformat() == "2026-07-29T16:00:00+00:00"
    assert reminder_today.assignments == {}
    assert reminder_today.deadline_start_utc == task_today.deadline_start_utc
    assert reminder_today.deadline_end_utc == task_today.deadline_end_utc
    assert mixed_deadline.deadline_start_utc is None
    assert mixed_deadline.deadline_end_utc.isoformat() == "2026-07-30T16:00:00+00:00"


def test_fixture_hash_covers_schema_relations_auxiliary_data_and_permissions() -> None:
    snapshot = _fixture_snapshot()

    assert snapshot["schema_version"] == "stage12-evaluation-fixture.v2"
    assert set(snapshot["tables"]) == {
        "projects",
        "work_items",
        "risks",
        "tasks",
        "owners",
        "daily_metrics",
        "interactions",
    }
    assert snapshot["relations"]
    assert snapshot["permission_profile"]
    assert snapshot["record_versions"]
    assert "due_date" in {
        field["key"] for field in snapshot["tables"]["tasks"]["fields"]
    }


def test_fixture_semantic_validator_rejects_wrong_field_type_and_unknown_action_field() -> (
    None
):
    cases = build_stage12_truth_cases()
    validate_truth_against_fixture(cases, _fixture_snapshot())
    risk_02 = next(item for item in cases if item.case_id == "risk_02")
    fact = risk_02.expected_task_spec.objectives[0]
    bad_predicate = fact.predicates[0].model_copy(update={"field_type": "text"})
    bad_fact = fact.model_copy(
        update={"predicates": (bad_predicate,) + fact.predicates[1:]}
    )
    bad_case = risk_02.model_copy(
        update={
            "expected_task_spec": risk_02.expected_task_spec.model_copy(
                update={
                    "objectives": (bad_fact,)
                    + risk_02.expected_task_spec.objectives[1:]
                }
            )
        }
    )

    with pytest.raises(ValueError, match="evaluation_fixture_predicate_type_mismatch"):
        validate_truth_against_fixture((bad_case,), _fixture_snapshot())

    draft = next(item for item in cases if item.case_id == "draft_01")
    slot = draft.expected_task_spec.action_slots[0]
    bad_slot = slot.model_copy(update={"required_fields": ("unknown_field",)})
    bad_action_case = draft.model_copy(
        update={
            "expected_task_spec": draft.expected_task_spec.model_copy(
                update={"action_slots": (bad_slot,)}
            )
        }
    )
    with pytest.raises(ValueError, match="evaluation_fixture_action_field_unknown"):
        validate_truth_against_fixture((bad_action_case,), _fixture_snapshot())


def test_permission_truth_is_explicit_for_all_permission_cases() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}

    assert by_id["permission_01"].expected_permission_outcome == "denied"
    assert by_id["permission_02"].expected_permission_outcome == "denied"
    assert by_id["permission_03"].expected_permission_outcome == "denied"
    assert by_id["permission_04"].expected_permission_outcome == "partial"
    assert by_id["mixed_05"].expected_permission_outcome == "partial"
    assert by_id["mixed_06"].expected_permission_outcome == "partial"
    assert by_id["mixed_08"].expected_permission_outcome == "allowed"


def test_approved_human_gold_denials_minimize_values_and_recipient_inference() -> None:
    by_id = {item.case_id: item for item in build_stage12_truth_cases()}

    for case_id, slot_index in (
        ("draft_02", 0),
        ("permission_02", 0),
        ("fault_02", 0),
        ("mixed_01", 0),
        ("mixed_08", 0),
    ):
        slot = by_id[case_id].expected_task_spec.action_slots[slot_index]
        assert slot.expected_outcome == "denied"
        assert slot.assignments == {}, case_id

    assert (
        by_id["draft_02"].expected_task_spec.action_slots[0].denial_reason
        == "field_permission_denied"
    )
    for case_id in ("reminder_02", "reminder_04"):
        slot = by_id[case_id].expected_task_spec.action_slots[0]
        assert slot.expected_outcome == "denied"
        assert slot.denial_reason == "action_recipient_unavailable"

    permission_query = by_id["permission_02"].expected_query_result
    assert permission_query.required_result_records == ()
    assert permission_query.allowed_evidence_records == ()


def test_audit_hashes_match_fixture_legacy_and_v2_payloads() -> None:
    cases = build_stage12_truth_cases()
    by_id = {item.case_id: item for item in cases}
    legacy = {item.case_id: item for item in build_complex_cases()}
    fixture_hash = canonical_sha256(_fixture_snapshot())
    report = load_gold_audit_report(DEFAULT_GOLD_AUDIT_PATH)
    report_by_id = {entry.case_id: entry.audit for entry in report.entries}

    assert report.fixture_hash == fixture_hash
    for case_id, case in by_id.items():
        assert case.gold_audit.source_fixture_hash == fixture_hash
        assert case.gold_audit.legacy_case_hash == canonical_sha256(
            asdict(legacy[case_id])
        )
        assert case.gold_audit.v2_case_hash == canonical_sha256(
            case_payload_for_hash(case)
        )
        assert case.gold_audit.status == "human_approved"
        assert report_by_id[case_id] == case.gold_audit


def test_audit_report_is_recomputed_from_truth_legacy_and_fixture() -> None:
    cases = build_stage12_truth_cases()

    report = audit_truth_set(
        cases,
        tuple(build_complex_cases()),
        _fixture_snapshot(),
    )

    assert report == load_gold_audit_report(DEFAULT_GOLD_AUDIT_PATH)
