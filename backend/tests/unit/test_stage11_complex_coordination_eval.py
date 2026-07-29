from scripts.stage11_complex_coordination_eval import (
    ExpectedAction,
    build_complex_cases,
    offline_plan_report,
)
from scripts.stage11_real_complex_report import _proposal_fields_correct


def test_complex_truth_set_has_48_chinese_cases_and_required_distribution() -> None:
    cases = build_complex_cases()

    assert len(cases) == 48
    assert len({item.query for item in cases}) == 48
    assert sum(item.category == "multi_intent" for item in cases) == 8
    assert all(any("\u3400" <= char <= "\u9fff" for char in item.query) for item in cases)
    assert all(
        len(item.objectives) >= 3
        for item in cases
        if item.category == "multi_intent"
    )
    multi_intent = [item for item in cases if item.category == "multi_intent"]
    assert sum(bool(item.expected_actions) for item in multi_intent) == 7
    assert sum(len(item.expected_actions) > 1 for item in multi_intent) >= 5


def test_offline_plan_report_exposes_routing_failures_instead_of_hiding_them() -> None:
    report = offline_plan_report(build_complex_cases())

    assert report["case_count"] == 48
    assert 0 <= report["capability_precision"] <= 1
    assert 0 <= report["capability_recall"] <= 1
    assert 0 <= report["objective_precision"] <= 1
    assert 0 <= report["objective_recall"] <= 1
    assert len(report["cases"]) == 48
    assert all("objective_exact_match" in item for item in report["cases"])


def test_proposal_field_accuracy_rejects_missing_null_and_placeholder_values() -> None:
    expected = ExpectedAction(
        "create_task",
        "TASKS",
        ("title", "project_link"),
        "pending_confirmation",
    )

    assert _proposal_fields_correct(
        expected,
        {"provider_status": "proposed", "proposed_values": {"title": "跟进", "project_link": "PRJ-ATLAS"}},
    )
    assert not _proposal_fields_correct(
        expected,
        {"provider_status": "proposed", "proposed_values": {"title": "跟进", "project_link": "关联项目"}},
    )
    assert not _proposal_fields_correct(
        expected,
        {"provider_status": "proposed", "proposed_values": {"title": "跟进"}},
    )
