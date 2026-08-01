from datetime import UTC, datetime
from pathlib import Path

from scripts.stage12_specialist_provider_evaluation import (
    SpecialistProviderEvaluationReportV1,
    main as evaluation_main,
    run_specialist_provider_evaluation,
)


NOW = datetime(2026, 7, 30, 10, 0, tzinfo=UTC)


def test_focused_evaluation_executes_four_handlers_and_safe_fan_in() -> None:
    report = run_specialist_provider_evaluation(now=lambda: NOW)

    assert isinstance(report, SpecialistProviderEvaluationReportV1)
    assert report.handler_count == 4
    assert report.contract_exact_count == 4
    assert report.claim_count >= 2
    assert report.valid_evidence_count >= 1
    assert report.partial_failure_safe is True
    assert report.stable_failure_class_count == 15
    assert report.chinese_answer_grounded is True
    assert report.provider_attempt_count == 0
    assert report.action_proposal_count == 1
    assert report.write_count == 0
    assert report.send_count == 0
    rendered = report.model_dump_json()
    for forbidden in ("query", "evidence_id", "candidate", "prompt", "阻塞"):
        assert forbidden not in rendered


def test_evaluation_cli_writes_hash_valid_sanitized_json(tmp_path: Path) -> None:
    output = tmp_path / "stage12-e.json"
    assert evaluation_main(["--output-json", str(output)], now=lambda: NOW) == 0
    report = SpecialistProviderEvaluationReportV1.model_validate_json(
        output.read_text(encoding="utf-8")
    )
    assert report.contract_exact_count == 4
    assert report.report_hash
