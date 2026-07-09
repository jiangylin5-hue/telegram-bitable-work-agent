from pathlib import Path

from scripts.stage06_skill_hit_rate_eval import (
    DEFAULT_GATES,
    evaluate_cases,
    load_cases,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "stage06_skill_matching_cases.json"
)

ACTIVE_CORE_SKILLS = {
    "platform-approval",
    "platform-base",
    "platform-contact",
    "platform-event",
    "platform-file-import",
    "platform-shared-policy",
    "platform-skill-maker",
    "platform-tabular-analysis",
    "platform-task",
    "platform-telegram-im",
    "platform-tool-discovery",
}


def test_stage06_skill_hit_rate_fixture_meets_minimum_shape() -> None:
    cases = load_cases(FIXTURE_PATH)

    assert len(cases) >= 108
    assert {case["case_id"] for case in cases}
    assert {case["skill_id"] for case in cases if case["group"] == "positive"} == (
        ACTIVE_CORE_SKILLS
    )

    for skill_id in ACTIVE_CORE_SKILLS:
        positives = [
            case
            for case in cases
            if case["skill_id"] == skill_id and case["group"] == "positive"
        ]
        negatives = [
            case
            for case in cases
            if case["skill_id"] == skill_id and case["group"] == "negative"
        ]
        assert len(positives) >= 5
        assert len(negatives) >= 3


def test_stage06_skill_hit_rate_benchmark_meets_stage06_gates() -> None:
    result = evaluate_cases(load_cases(FIXTURE_PATH), gates=DEFAULT_GATES)

    assert result["ok"] is True
    assert result["case_count"] >= 108
    assert result["metrics"]["top1_accuracy"] >= DEFAULT_GATES["top1_accuracy"]
    assert result["metrics"]["top3_recall"] >= DEFAULT_GATES["top3_recall"]
    assert result["metrics"]["high_risk_false_commit_routes"] == 0
    assert result["metrics"]["hidden_or_unauthorized_false_positive"] == 0
    assert (
        result["metrics"]["missing_context_clarification_rate"]
        >= DEFAULT_GATES["missing_context_clarification_rate"]
    )
    assert (
        result["metrics"]["evidence_presence_rate"]
        == DEFAULT_GATES["evidence_presence_rate"]
    )
    assert result["failures"] == []


def test_stage06_skill_hit_rate_benchmark_keeps_fixture_generic() -> None:
    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")

    assert "recharge" not in fixture_text.lower()
    assert "bm invite" not in fixture_text.lower()
    assert "card binding" not in fixture_text.lower()
    assert "ad account" not in fixture_text.lower()
