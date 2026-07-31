from __future__ import annotations

import json

import scripts.stage12_query_engine_evaluation as evaluation


def test_gold_is_read_only_after_compile_and_execute_complete(monkeypatch) -> None:
    execution_complete = {"value": False}
    real_execute = evaluation.execute_authorized_query
    real_gold_reader = evaluation._read_expected_query_result

    def tracked_execute(*args, **kwargs):
        artifact = real_execute(*args, **kwargs)
        execution_complete["value"] = True
        return artifact

    def guarded_gold_reader(case):
        assert execution_complete["value"] is True
        return real_gold_reader(case)

    monkeypatch.setattr(evaluation, "execute_authorized_query", tracked_execute)
    monkeypatch.setattr(evaluation, "_read_expected_query_result", guarded_gold_reader)

    report = evaluation.run_stage12_query_engine_evaluation(case_ids=("daily_04",))

    assert report["raw_case_count"] == 1
    assert report["applicable_case_count"] == 1
    assert report["cases"][0]["status"] == "executed"


def test_bounded_report_excludes_action_expansion_and_external_effects() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(
        case_ids=("join_08", "daily_04", "risk_04")
    )

    assert report["raw_case_count"] == 3
    assert report["applicable_case_count"] == 3
    assert report["execution_boundary"] == {
        "provider_calls": 0,
        "action_expansions": 0,
        "record_writes_after_fixture_setup": 0,
        "external_sends": 0,
    }
    serialized = json.dumps(report, ensure_ascii=False)
    assert "expected_query_result" not in serialized
    assert "action_slots" not in serialized
    assert "target_selector" not in serialized
    assert all(item["permission_safe"] is True for item in report["cases"])


def test_applicable_denominator_excludes_cases_without_structured_query_truth() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(
        case_ids=("join_01", "permission_01")
    )

    assert report["raw_case_count"] == 2
    assert report["applicable_case_count"] == 1
    by_case = {item["case_id"]: item for item in report["cases"]}
    assert by_case["join_01"]["applicable"] is True
    assert by_case["permission_01"]["applicable"] is False
    assert by_case["permission_01"]["case_exact"] is None


def test_case_exact_scores_aggregate_and_stable_sort_contracts() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(case_ids=("daily_04",))

    assert report["applicable_case_count"] == 1
    row = report["cases"][0]
    assert row["aggregate_exact"] is True
    assert row["sort_exact"] is True
    assert row["case_exact"] is True
    assert report["aggregate_applicable_case_count"] == 1
    assert report["aggregate_exact_case_count"] == 1
    assert report["sort_applicable_case_count"] == 1
    assert report["sort_exact_case_count"] == 1


def test_conditional_aggregate_evidence_excludes_non_contributing_rows() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(case_ids=("daily_01",))

    row = report["cases"][0]
    assert row["aggregate_exact"] is True
    assert row["actual_record_codes"] == row["allowed_evidence_codes"]
    assert row["case_exact"] is True


def test_risk_record_language_is_distinguished_from_work_item_risk_fields() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(
        case_ids=("risk_01", "risk_02", "risk_05")
    )

    assert all(row["case_exact"] is True for row in report["cases"])


def test_context_paths_are_planned_without_polluting_action_evidence() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(
        case_ids=("draft_04", "draft_05", "draft_06", "task_01", "task_03")
    )

    assert all(row["case_exact"] is True for row in report["cases"])


def test_permission_conflict_and_stale_version_queries_do_not_invent_joins() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(
        case_ids=("permission_02", "fault_02", "mixed_06", "mixed_08")
    )

    by_id = {row["case_id"]: row for row in report["cases"]}
    assert by_id["permission_02"]["applicable"] is False
    assert by_id["permission_02"]["case_exact"] is None
    assert all(
        by_id[case_id]["case_exact"] is True
        for case_id in ("fault_02", "mixed_06", "mixed_08")
    )


def test_risk_aggregates_match_group_and_filter_contracts() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(
        case_ids=("risk_03", "risk_06")
    )

    assert all(row["aggregate_exact"] is True for row in report["cases"])
    assert all(row["case_exact"] is True for row in report["cases"])


def test_mixed_query_contracts_keep_query_and_action_context_separate() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(
        case_ids=("mixed_01", "mixed_02", "mixed_03", "mixed_04", "mixed_07")
    )

    assert all(row["case_exact"] is True for row in report["cases"])


def test_action_only_risk_evidence_path_is_not_scored_as_a_result_join() -> None:
    report = evaluation.run_stage12_query_engine_evaluation(case_ids=("mixed_07",))

    row = report["cases"][0]
    assert row["actual_relation_paths"] == [
        ("work_items.owner_link",),
        ("work_items.project_link",),
    ]
    assert row["relation_exact"] is True
    assert row["case_exact"] is True


def test_all_join_gold_cases_remain_exact_after_optional_path_optimization() -> None:
    case_ids = tuple(f"join_{index:02d}" for index in range(1, 9))
    report = evaluation.run_stage12_query_engine_evaluation(case_ids=case_ids)

    assert report["applicable_case_count"] == 8
    assert report["exact_case_count"] == 8
    assert all(row["case_exact"] is True for row in report["cases"])
