from scripts.stage12_planner_v2_evaluation import (
    run_stage12_planner_v2_evaluation,
)


def test_stage12_planner_v2_evaluation_is_bounded_and_planner_only() -> None:
    report = run_stage12_planner_v2_evaluation()

    assert report["version"] == "stage12-planner-v2-evaluation.v1"
    assert report["case_count"] == 48
    assert len(report["cases"]) == 48
    assert report["execution_boundary"] == {
        "provider_calls": 0,
        "query_executions": 0,
        "record_writes": 0,
        "external_sends": 0,
    }
    assert report["metrics"]["planning_error_count"] >= 0
    assert 0.0 <= report["metrics"]["objective_precision_mean"] <= 1.0
    assert 0.0 <= report["metrics"]["objective_recall_mean"] <= 1.0
    assert all(
        case["planner_observation_status"] in {"observed", "planning_error"}
        for case in report["cases"]
    )
    cases = {case["case_id"]: case for case in report["cases"]}
    assert cases["daily_04"]["predicate_exact"] is True
    assert cases["mixed_03"]["predicate_exact"] is True
    metrics = report["stage12_b_metrics"]
    assert metrics["objective_exact"]["accuracy"] >= 0.90
    assert metrics["predicate_exact"]["accuracy"] >= 0.90
    assert metrics["action_template_exact"]["accuracy"] >= 0.90
    assert metrics["gates_pass"] is True
    assert cases["reminder_03"]["stage12_b_action_template_exact"] is True
    assert cases["mixed_01"]["stage12_b_action_template_exact"] is True
    assert cases["risk_01"]["stage12_b_objective_status"] == "truth_review_required"
