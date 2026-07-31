from __future__ import annotations

import pytest

import scripts.stage12_real_quality_report as report_module
from scripts.stage12_quality_evaluation import (
    ActionScore,
    AnswerScore,
    CaseScoreV2,
    DurabilityScore,
    FinalAnswerQualityScoreV2,
    LatencyPercentiles,
    LatencyScore,
    PlannerScore,
    ProviderTrace,
    QueryScore,
    RetrievalScore,
    RuntimeAnswerTrace,
    RuntimeDurabilityTrace,
    RuntimeLatencyTrace,
    RuntimeQueryTrace,
    RuntimeRetrievalTrace,
    RuntimeSafetyTrace,
    RuntimeTraceV2,
    SafetyScore,
    build_stage12_truth_cases,
)
from scripts.stage12_real_quality_report import (
    EvaluationReportV2,
    EvaluationResultV2,
    build_execution_request,
    run_v2_report,
    validate_no_gold_leak,
)


def _case(case_id: str):
    return next(case for case in build_stage12_truth_cases() if case.case_id == case_id)


def _unobserved_trace(case_id: str, round_id: str) -> RuntimeTraceV2:
    return RuntimeTraceV2(
        version="runtime-trace.v2",
        case_id=case_id,
        round_id=round_id,
        provider=ProviderTrace(
            provider="deterministic",
            model="none",
            profile="stage12-focused",
        ),
        planner=None,
        specialists=(),
        query=RuntimeQueryTrace(
            observation_status="not_observed",
            result_record_ids=(),
            evidence_record_ids=(),
            predicates=(),
            relation_paths=(),
            aggregates=(),
            facts=(),
            complete=False,
        ),
        retrieval=RuntimeRetrievalTrace(
            observation_status="not_observed",
            candidate_record_ids=(),
            selected_evidence_record_ids=(),
            candidate_table_by_record={},
            relation_paths=(),
            complete=False,
        ),
        answer=RuntimeAnswerTrace(
            observation_status="not_observed",
            rendered_answer="",
            claims=(),
            answer_source="deterministic_fallback",
            provider_result_status="transport_failed",
        ),
        actions=(),
        safety=RuntimeSafetyTrace(
            permission_outcome="allowed",
            unauthorized_effect_count=0,
            external_send_count=0,
        ),
        durability=RuntimeDurabilityTrace(
            terminal=True,
            recovery_expectation="not_applicable",
            recovered=False,
            idempotent=True,
            duplicate_effect_count=0,
        ),
        latency=RuntimeLatencyTrace(segments_ms={"total": 1}),
    )


def _literal_score(
    *,
    objective_exact: bool | None = True,
    external_send_safe: bool = True,
    latency_ms: float = 1000.0,
    final_answer_grounded: bool = True,
) -> CaseScoreV2:
    planner_observed = objective_exact is not None
    return CaseScoreV2(
        planner=PlannerScore(
            observation_status="observed" if planner_observed else "not_observed",
            objective_precision=1.0 if planner_observed else None,
            objective_recall=1.0 if planner_observed else None,
            objective_exact=objective_exact,
            dependency_edge_exact=True if planner_observed else None,
            predicate_exact=True if planner_observed else None,
            gate_pass=objective_exact is True,
        ),
        query=QueryScore(
            observation_status="observed",
            filter_precision=1.0,
            filter_recall=1.0,
            filter_exact=True,
            aggregate_exact=True,
            join_path_exact=True,
            sort_exact=True,
            forbidden_result_count=0,
            gate_pass=True,
        ),
        retrieval=RetrievalScore(
            observation_status="not_applicable",
            k=20,
            candidate_recall_at_k=None,
            candidate_precision_at_k=None,
            selected_evidence_recall=None,
            selected_evidence_precision=None,
            per_table_recall={},
            join_path_exact=None,
            forbidden_candidate_count=None,
            gate_pass=True,
        ),
        answer=AnswerScore(
            observation_status="observed",
            grounded_claim_precision=1.0,
            required_fact_recall=1.0,
            unsupported_claim_rate=0.0,
            aggregate_exact=True,
            gate_pass=True,
        ),
        final_answer=FinalAnswerQualityScoreV2(
            observation_status="observed",
            factual_correctness=True,
            required_result_completeness=True,
            relation_aggregate_correctness=True,
            citation_to_fact_grounding=final_answer_grounded,
            instruction_action_satisfaction=True,
            chinese_clarity=True,
            refusal_degradation_appropriateness=True,
            real_provider_origin=True,
            reason_codes=(
                () if final_answer_grounded else ("citation_grounding_failed",)
            ),
            gate_pass=final_answer_grounded,
        ),
        action=ActionScore(
            observation_status="observed",
            mode="end_to_end",
            slot_accuracy=1.0,
            target_accuracy=1.0,
            field_accuracy=1.0,
            value_accuracy=1.0,
            deadline_accuracy=1.0,
            confirmation_accuracy=1.0,
            proposal_schema_accuracy=1.0,
            persistence_accuracy=1.0,
            denial_reason_accuracy=1.0,
            external_effect_safety=1.0,
            gate_pass=True,
        ),
        safety=SafetyScore(
            permission_safety=1.0,
            external_send_safety=1.0 if external_send_safe else 0.0,
            gate_pass=external_send_safe,
        ),
        durability=DurabilityScore(
            terminal_accuracy=1.0,
            recovery_applicability="required",
            recovery_accuracy=1.0,
            idempotency_accuracy=1.0,
            duplicate_effect_safety=1.0,
            gate_pass=True,
        ),
        latency=LatencyScore(
            sample_count=1,
            segments={
                "total": LatencyPercentiles(
                    p50_ms=latency_ms,
                    p95_ms=latency_ms,
                    p99_ms=latency_ms,
                )
            },
        ),
        informational_score=1.0,
        release_gate_pass=(
            objective_exact is True and external_send_safe and final_answer_grounded
        ),
    )


def _literal_three_round_report(
    *,
    objective_exact_counts: tuple[int, int, int] = (48, 48, 48),
    missing_objective: bool = False,
    safety_failure: bool = False,
    one_latency_outlier: bool = False,
    final_answer_failure: bool = False,
) -> EvaluationReportV2:
    results: list[EvaluationResultV2] = []
    for round_number, exact_count in enumerate(objective_exact_counts, start=1):
        round_id = f"round-{round_number:02d}"
        for case_number in range(48):
            case_id = f"case-{case_number + 1:02d}"
            objective_exact: bool | None = case_number < exact_count
            if missing_objective and round_number == 1 and case_number == 0:
                objective_exact = None
            external_send_safe = not (
                safety_failure and round_number == 3 and case_number == 47
            )
            latency_ms = (
                9000.0
                if one_latency_outlier and round_number == 1 and case_number == 47
                else 1000.0
            )
            final_answer_grounded = not (
                final_answer_failure and round_number == 2 and case_number == 0
            )
            results.append(
                EvaluationResultV2(
                    case_id=case_id,
                    round_id=round_id,
                    trace=_unobserved_trace(case_id, round_id),
                    score=_literal_score(
                        objective_exact=objective_exact,
                        external_send_safe=external_send_safe,
                        latency_ms=latency_ms,
                        final_answer_grounded=final_answer_grounded,
                    ),
                )
            )
    return EvaluationReportV2(
        version="evaluation-report.v2",
        case_count=48,
        rounds=3,
        materialize_actions=True,
        results=tuple(results),
    )


def _summarize(report: EvaluationReportV2):
    return report_module.summarize_final_campaign(
        report,
        human_gold_approved_count=48,
        retrieval_candidate_recall_at_20_by_round=(0.96, 0.96, 0.96),
        provider_required_count_by_round=(100, 100, 100),
        provider_unavailable_count_by_round=(0, 0, 0),
        confirmed_action_count_by_round=(0, 0, 0),
        production_write_count_by_round=(0, 0, 0),
        telegram_send_count_by_round=(0, 0, 0),
    )


def test_execution_request_contains_query_and_authorized_runtime_context_only() -> None:
    case = _case("draft_01")
    request = build_execution_request(
        case,
        round_id="round-01",
        runtime_context={
            "workspace_id": "workspace-1",
            "authorized_candidate_ids": ["MT-014", "MT-020"],
        },
        materialize_actions=False,
    )

    validate_no_gold_leak(request, case)

    assert request["query"] == case.query
    assert set(request) == {"query", "round_id", "runtime_context"}
    assert "case_id" not in request
    assert "materialize_actions" not in request
    assert request["runtime_context"]["materialize_actions"] is False
    assert request["runtime_context"]["execution_id"].startswith("execution:sha256:")
    assert "expected_task_spec" not in request
    assert "expected_query_result" not in request
    assert "gold_audit" not in request


def test_gold_leak_validator_rejects_expected_action_target_field_and_value() -> None:
    case = _case("draft_01")
    leaked = {
        "query": case.query,
        "expected_action_kind": "record.update",
        "target_selector": {"record_code": "MT-014"},
        "required_fields": ["status"],
        "assignments": {"status": "in_progress"},
    }

    try:
        validate_no_gold_leak(leaked, case)
    except ValueError as exc:
        assert str(exc) == "evaluation_gold_leak_detected"
    else:  # pragma: no cover - explicit leak must fail
        raise AssertionError("gold leak was not rejected")

    try:
        validate_no_gold_leak(
            {"query": case.query, "action_kind": "record.update"}, case
        )
    except ValueError as exc:
        assert str(exc) == "evaluation_gold_leak_detected"
    else:  # pragma: no cover - direct action kind must fail
        raise AssertionError("action kind leak was not rejected")

    with pytest.raises(ValueError, match="evaluation_gold_leak_detected"):
        build_execution_request(
            case,
            round_id="round-01",
            runtime_context={
                "isolated": {
                    "expected_result_record_ids": ["MT-014"],
                }
            },
            materialize_actions=False,
        )


def test_runner_hands_gold_only_to_scorer_after_execution() -> None:
    case = _case("join_01")
    captured: list[dict[str, object]] = []

    def execute(request: dict[str, object]) -> RuntimeTraceV2:
        captured.append(request)
        return _unobserved_trace(
            str(request["runtime_context"]["execution_id"]),
            str(request["round_id"]),
        )

    report = run_v2_report(
        cases=(case,),
        execute=execute,
        rounds=1,
        runtime_context={"workspace_id": "workspace-1"},
        materialize_actions=False,
    )

    assert len(captured) == 1
    assert set(captured[0]) == {
        "query",
        "round_id",
        "runtime_context",
    }
    assert report.results[0].trace.case_id == "join_01"
    assert report.case_count == 1
    assert report.rounds == 1
    assert report.results[0].case_id == "join_01"
    assert report.results[0].score.release_gate_pass is False


def test_final_summary_reports_hand_derived_round_statistics() -> None:
    report = _literal_three_round_report(objective_exact_counts=(48, 24, 0))

    summary = _summarize(report)
    objective = summary.metrics["objective_exact"]

    assert objective.round_values == (1.0, 0.5, 0.0)
    assert objective.mean == pytest.approx(0.5)
    assert objective.worst == 0.0
    assert objective.population_variance == pytest.approx(1.0 / 6.0)
    assert objective.population_standard_deviation == pytest.approx((1.0 / 6.0) ** 0.5)
    assert objective.gate_pass is False
    assert summary.release_gate_pass is False


def test_final_summary_does_not_average_away_one_safety_failure() -> None:
    report = _literal_three_round_report(safety_failure=True)

    summary = _summarize(report)

    assert summary.metrics["external_send_safety"].mean == pytest.approx(143 / 144)
    assert summary.metrics["external_send_safety"].gate_pass is False
    assert summary.release_gate_pass is False


def test_final_summary_does_not_average_away_one_final_answer_failure() -> None:
    report = _literal_three_round_report(final_answer_failure=True)

    summary = _summarize(report)

    metric = summary.metrics["final_answer_citation_grounding"]
    assert metric.mean == pytest.approx(143 / 144)
    assert metric.worst == pytest.approx(47 / 48)
    assert metric.population_variance > 0.0
    assert metric.gate_pass is False
    assert summary.release_gate_pass is False


def test_final_summary_fails_closed_when_one_required_observation_is_missing() -> None:
    report = _literal_three_round_report(missing_objective=True)

    summary = _summarize(report)

    assert summary.metrics["objective_exact"].observed_count == 143
    assert summary.metrics["objective_exact"].expected_count == 144
    assert summary.metrics["objective_exact"].gate_pass is False
    assert summary.release_gate_pass is False


def test_final_summary_passes_only_when_every_named_gate_passes() -> None:
    report = _literal_three_round_report()

    summary = _summarize(report)

    assert summary.human_gold_approved_count == 48
    assert summary.case_count == 48
    assert summary.rounds == 3
    assert summary.metrics["objective_exact"].mean == 1.0
    assert summary.metrics["retrieval_candidate_recall_at_20"].mean == 0.96
    assert summary.metrics["p95_total_latency_ms"].worst == 1000.0
    assert summary.release_gate_pass is True


def test_final_summary_uses_round_p95_instead_of_mean_latency() -> None:
    report = _literal_three_round_report(one_latency_outlier=True)

    summary = _summarize(report)

    assert summary.metrics["p95_total_latency_ms"].round_values == (
        1000.0,
        1000.0,
        1000.0,
    )
    assert summary.metrics["p95_total_latency_ms"].gate_pass is True
