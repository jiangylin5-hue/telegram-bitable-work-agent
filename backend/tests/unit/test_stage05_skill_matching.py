import json
from pathlib import Path

import pytest


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "stage05_skill_cases.json"
)


@pytest.mark.parametrize("case", json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
def test_stage05_skill_matching_uses_fixture_expected_skills(
    case: dict[str, object],
) -> None:
    from app.agents.schemas import RouterResult
    from app.agents.stage05_skill_matching import build_skill_evidence

    router_result = RouterResult.model_validate(case["router_result"])
    evidence = build_skill_evidence(
        router_result=router_result,
        source_text_summary=str(case["source_text_summary"]),
    )

    selected_ids = {item["skill_id"] for item in evidence["selected_skills"]}
    future_ids = {item["skill_id"] for item in evidence["future_scope_skills"]}

    assert set(case["expected_selected_skills"]).issubset(selected_ids)
    assert set(case["expected_future_scope_skills"]).issubset(future_ids)
    assert evidence["manifest_version"] == "stage05-skills-v1"
    assert evidence["mode"] == "sidecar_candidate_logging"
    assert evidence["baseline_metrics"]["selected_count"] == len(
        evidence["selected_skills"]
    )


def test_stage05_skill_matching_rejects_report_draft_registration() -> None:
    from app.agents.schemas import RouterResult
    from app.agents.stage05_skill_matching import build_skill_evidence

    router_result = RouterResult.model_validate(
        {
            "intents": [
                {
                    "intent_type": "report_request",
                    "confidence": "0.9000",
                    "entities": {"report_type": "customer_daily"},
                    "risk_flags": ["customer_group_send_requested"],
                    "missing_context": [],
                }
            ],
            "overall_confidence": "0.9000",
            "requires_manual_review": True,
            "manual_review_reasons": ["reporting_future_scope"],
            "redacted_summary": "Customer asks for report generation.",
        }
    )

    evidence = build_skill_evidence(
        router_result=router_result,
        source_text_summary="Generate today's report.",
    )

    selected_ids = {item["skill_id"] for item in evidence["selected_skills"]}
    rejected_ids = {item["skill_id"] for item in evidence["rejected_skills"]}

    assert "report-draft" not in selected_ids
    assert "report-draft" in rejected_ids
    assert evidence["fallback"] in {"manual_review", "future_scope"}
