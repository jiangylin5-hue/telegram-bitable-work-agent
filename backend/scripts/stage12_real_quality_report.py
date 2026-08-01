"""Leak-free Stage12 Evaluation V2 report runner.

Gold truth is held by the report process and reaches only the scorer after an
execution callback has returned a runtime trace.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
from math import sqrt
from typing import Literal

from pydantic import Field, StrictBool, StrictFloat, StrictInt

from scripts.stage12_quality_evaluation import (
    CaseScoreV2,
    EvaluationCaseV2,
    NonEmptyStr,
    RuntimeTraceV2,
    _StrictFrozenModel,
    score_case_v2,
)


_FORBIDDEN_GOLD_KEYS = {
    "action_kind",
    "expected",
    "expected_action",
    "expected_action_kind",
    "expected_outcome",
    "expected_query_result",
    "expected_status",
    "expected_task_spec",
    "gold",
    "gold_audit",
    "target_selector",
    "required_fields",
    "assignments",
}


class EvaluationResultV2(_StrictFrozenModel):
    case_id: NonEmptyStr
    round_id: NonEmptyStr
    trace: RuntimeTraceV2
    score: CaseScoreV2


class EvaluationReportV2(_StrictFrozenModel):
    version: Literal["evaluation-report.v2"]
    case_count: StrictInt = Field(ge=1)
    rounds: StrictInt = Field(ge=1)
    materialize_actions: StrictBool
    results: tuple[EvaluationResultV2, ...]


class CampaignDistributionV2(_StrictFrozenModel):
    round_values: tuple[StrictFloat, ...]
    mean: StrictFloat
    worst: StrictFloat
    population_variance: StrictFloat = Field(ge=0.0)
    population_standard_deviation: StrictFloat = Field(ge=0.0)
    observed_count: StrictInt = Field(ge=0)
    expected_count: StrictInt = Field(ge=1)


class CampaignMetricSummaryV2(CampaignDistributionV2):
    comparison: Literal["at_least", "at_most", "exact"]
    target: StrictFloat
    gate_pass: StrictBool


class FinalCampaignSummaryV2(_StrictFrozenModel):
    version: Literal["final-campaign-summary.v2"]
    case_count: StrictInt = Field(ge=1)
    rounds: StrictInt = Field(ge=1)
    human_gold_approved_count: StrictInt = Field(ge=0)
    metrics: dict[NonEmptyStr, CampaignMetricSummaryV2]
    case_failure_rate: CampaignDistributionV2
    release_gate_pass: StrictBool


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in _FORBIDDEN_GOLD_KEYS or normalized.startswith("gold_"):
                return True
            if normalized.startswith("expected_"):
                return True
            if _contains_forbidden_key(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def validate_no_gold_leak(
    execution_request: object,
    case: EvaluationCaseV2,
) -> None:
    del case
    if _contains_forbidden_key(execution_request):
        raise ValueError("evaluation_gold_leak_detected")


def build_execution_request(
    case: EvaluationCaseV2,
    *,
    round_id: str,
    runtime_context: Mapping[str, object],
    materialize_actions: bool,
) -> dict[str, object]:
    context = dict(runtime_context)
    if {"execution_id", "materialize_actions"}.intersection(context):
        raise ValueError("evaluation_runtime_context_reserved_key")
    execution_id = (
        "execution:sha256:"
        + hashlib.sha256(f"{round_id}\x1f{case.query}".encode("utf-8")).hexdigest()
    )
    context.update(
        {
            "execution_id": execution_id,
            "materialize_actions": materialize_actions,
        }
    )
    request: dict[str, object] = {
        "query": case.query,
        "round_id": round_id,
        "runtime_context": context,
    }
    validate_no_gold_leak(request, case)
    return request


def run_v2_report(
    *,
    cases: tuple[EvaluationCaseV2, ...],
    execute: Callable[[dict[str, object]], RuntimeTraceV2],
    rounds: int,
    runtime_context: Mapping[str, object],
    materialize_actions: bool,
) -> EvaluationReportV2:
    if not cases:
        raise ValueError("evaluation_report_cases_empty")
    if rounds < 1:
        raise ValueError("evaluation_report_rounds_invalid")
    results: list[EvaluationResultV2] = []
    for round_number in range(1, rounds + 1):
        round_id = f"round-{round_number:02d}"
        for case in cases:
            request = build_execution_request(
                case,
                round_id=round_id,
                runtime_context=runtime_context,
                materialize_actions=materialize_actions,
            )
            trace = execute(request)
            execution_id = str(request["runtime_context"]["execution_id"])
            if trace.case_id != execution_id or trace.round_id != round_id:
                raise ValueError("evaluation_runtime_trace_identity_mismatch")
            trace = RuntimeTraceV2.model_validate(
                {
                    **trace.model_dump(mode="python"),
                    "case_id": case.case_id,
                }
            )
            score = score_case_v2(case, trace, action_mode="end_to_end")
            results.append(
                EvaluationResultV2(
                    case_id=case.case_id,
                    round_id=round_id,
                    trace=trace,
                    score=score,
                )
            )
    return EvaluationReportV2(
        version="evaluation-report.v2",
        case_count=len(cases),
        rounds=rounds,
        materialize_actions=materialize_actions,
        results=tuple(results),
    )


def _validated_round_results(
    report: EvaluationReportV2,
) -> tuple[tuple[EvaluationResultV2, ...], ...]:
    if report.case_count != 48 or report.rounds != 3:
        raise ValueError("evaluation_final_campaign_shape_invalid")
    if not report.materialize_actions:
        raise ValueError("evaluation_final_campaign_actions_not_materialized")
    grouped: dict[str, list[EvaluationResultV2]] = {}
    for result in report.results:
        grouped.setdefault(result.round_id, []).append(result)
    expected_round_ids = tuple(f"round-{index:02d}" for index in range(1, 4))
    if tuple(sorted(grouped)) != expected_round_ids:
        raise ValueError("evaluation_final_campaign_rounds_invalid")
    rounds = tuple(tuple(grouped[round_id]) for round_id in expected_round_ids)
    case_sets = tuple({result.case_id for result in values} for values in rounds)
    if any(len(values) != report.case_count for values in rounds):
        raise ValueError("evaluation_final_campaign_result_count_invalid")
    if any(len(case_ids) != report.case_count for case_ids in case_sets):
        raise ValueError("evaluation_final_campaign_case_ids_duplicate")
    if any(case_ids != case_sets[0] for case_ids in case_sets[1:]):
        raise ValueError("evaluation_final_campaign_case_ids_mismatch")
    return rounds


def _distribution(
    round_values: tuple[float, ...],
    *,
    observed_count: int,
    expected_count: int,
    worst_is_minimum: bool,
) -> CampaignDistributionV2:
    if not round_values:
        raise ValueError("evaluation_campaign_round_values_empty")
    mean = sum(round_values) / len(round_values)
    variance = sum((value - mean) ** 2 for value in round_values) / len(round_values)
    return CampaignDistributionV2(
        round_values=round_values,
        mean=float(mean),
        worst=float(min(round_values) if worst_is_minimum else max(round_values)),
        population_variance=float(variance),
        population_standard_deviation=float(sqrt(variance)),
        observed_count=observed_count,
        expected_count=expected_count,
    )


def _comparison_passes(
    value: float,
    *,
    comparison: Literal["at_least", "at_most", "exact"],
    target: float,
) -> bool:
    if comparison == "at_least":
        return value >= target
    if comparison == "at_most":
        return value <= target
    return value == target


def _metric_summary(
    round_results: tuple[tuple[EvaluationResultV2, ...], ...],
    *,
    extractor: Callable[[EvaluationResultV2], float | None],
    comparison: Literal["at_least", "at_most", "exact"],
    target: float,
) -> CampaignMetricSummaryV2:
    observed_count = 0
    expected_count = sum(len(values) for values in round_results)
    round_values: list[float] = []
    for results in round_results:
        total = 0.0
        for result in results:
            value = extractor(result)
            if value is None:
                continue
            observed_count += 1
            total += value
        round_values.append(total / len(results))
    distribution = _distribution(
        tuple(round_values),
        observed_count=observed_count,
        expected_count=expected_count,
        worst_is_minimum=comparison == "at_least" or target == 1.0,
    )
    return CampaignMetricSummaryV2(
        **distribution.model_dump(),
        comparison=comparison,
        target=float(target),
        gate_pass=(
            observed_count == expected_count
            and _comparison_passes(
                distribution.mean,
                comparison=comparison,
                target=target,
            )
        ),
    )


def _external_metric_summary(
    values: tuple[float, ...],
    *,
    comparison: Literal["at_least", "at_most", "exact"],
    target: float,
) -> CampaignMetricSummaryV2:
    distribution = _distribution(
        values,
        observed_count=len(values),
        expected_count=len(values),
        worst_is_minimum=comparison == "at_least" or target == 1.0,
    )
    return CampaignMetricSummaryV2(
        **distribution.model_dump(),
        comparison=comparison,
        target=float(target),
        gate_pass=_comparison_passes(
            distribution.mean,
            comparison=comparison,
            target=target,
        ),
    )


def _percentile(values: tuple[float, ...], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = tuple(sorted(values))
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _latency_metric_summary(
    round_results: tuple[tuple[EvaluationResultV2, ...], ...],
) -> CampaignMetricSummaryV2:
    observed_count = 0
    expected_count = sum(len(values) for values in round_results)
    round_values: list[float] = []
    for results in round_results:
        values: list[float] = []
        for result in results:
            segment = result.score.latency.segments.get("total")
            if segment is None:
                continue
            observed_count += 1
            values.append(float(segment.p95_ms))
        round_values.append(_percentile(tuple(values), 0.95))
    distribution = _distribution(
        tuple(round_values),
        observed_count=observed_count,
        expected_count=expected_count,
        worst_is_minimum=False,
    )
    return CampaignMetricSummaryV2(
        **distribution.model_dump(),
        comparison="at_most",
        target=8000.0,
        gate_pass=(observed_count == expected_count and distribution.worst <= 8000.0),
    )


def _bool_metric_value(value: bool | None) -> float | None:
    return None if value is None else float(value)


def _validated_round_tuple(
    values: tuple[int | float, ...],
    *,
    rounds: int,
    name: str,
    integer: bool,
) -> tuple[float, ...]:
    if len(values) != rounds:
        raise ValueError(f"evaluation_{name}_round_count_invalid")
    normalized: list[float] = []
    for value in values:
        if isinstance(value, bool) or (integer and not isinstance(value, int)):
            raise ValueError(f"evaluation_{name}_value_invalid")
        normalized_value = float(value)
        if normalized_value < 0:
            raise ValueError(f"evaluation_{name}_value_invalid")
        normalized.append(normalized_value)
    return tuple(normalized)


def summarize_final_campaign(
    report: EvaluationReportV2,
    *,
    human_gold_approved_count: int,
    retrieval_candidate_recall_at_20_by_round: tuple[float, ...],
    provider_required_count_by_round: tuple[int, ...],
    provider_unavailable_count_by_round: tuple[int, ...],
    confirmed_action_count_by_round: tuple[int, ...],
    production_write_count_by_round: tuple[int, ...],
    telegram_send_count_by_round: tuple[int, ...],
) -> FinalCampaignSummaryV2:
    """Summarize the approved three-round final campaign without hiding gaps."""

    if isinstance(human_gold_approved_count, bool) or human_gold_approved_count < 0:
        raise ValueError("evaluation_human_gold_approved_count_invalid")
    round_results = _validated_round_results(report)
    retrieval = _validated_round_tuple(
        retrieval_candidate_recall_at_20_by_round,
        rounds=report.rounds,
        name="retrieval_recall",
        integer=False,
    )
    if any(value > 1.0 for value in retrieval):
        raise ValueError("evaluation_retrieval_recall_value_invalid")
    required = _validated_round_tuple(
        provider_required_count_by_round,
        rounds=report.rounds,
        name="provider_required_count",
        integer=True,
    )
    unavailable = _validated_round_tuple(
        provider_unavailable_count_by_round,
        rounds=report.rounds,
        name="provider_unavailable_count",
        integer=True,
    )
    if any(total <= 0 for total in required) or any(
        missing > total for missing, total in zip(unavailable, required, strict=True)
    ):
        raise ValueError("evaluation_provider_observation_invalid")
    provider_unavailable_rates = tuple(
        missing / total for missing, total in zip(unavailable, required, strict=True)
    )
    fallback_counts = tuple(
        float(
            sum(item.trace.answer.answer_source != "real_provider" for item in results)
        )
        for results in round_results
    )
    confirmed = _validated_round_tuple(
        confirmed_action_count_by_round,
        rounds=report.rounds,
        name="confirmed_action_count",
        integer=True,
    )
    writes = _validated_round_tuple(
        production_write_count_by_round,
        rounds=report.rounds,
        name="production_write_count",
        integer=True,
    )
    sends = _validated_round_tuple(
        telegram_send_count_by_round,
        rounds=report.rounds,
        name="telegram_send_count",
        integer=True,
    )

    metrics = {
        "objective_exact": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.planner.objective_exact
            ),
            comparison="at_least",
            target=0.90,
        ),
        "predicate_exact": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.planner.predicate_exact
            ),
            comparison="at_least",
            target=0.90,
        ),
        "retrieval_candidate_recall_at_20": _external_metric_summary(
            retrieval,
            comparison="at_least",
            target=0.95,
        ),
        "final_record_precision": _metric_summary(
            round_results,
            extractor=lambda item: item.score.query.filter_precision,
            comparison="at_least",
            target=0.90,
        ),
        "final_record_recall": _metric_summary(
            round_results,
            extractor=lambda item: item.score.query.filter_recall,
            comparison="at_least",
            target=0.90,
        ),
        "join_path_accuracy": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(item.score.query.join_path_exact),
            comparison="at_least",
            target=0.95,
        ),
        "aggregate_exact": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(item.score.query.aggregate_exact),
            comparison="at_least",
            target=0.95,
        ),
        "unsupported_claim_rate": _metric_summary(
            round_results,
            extractor=lambda item: item.score.answer.unsupported_claim_rate,
            comparison="at_most",
            target=0.02,
        ),
        "final_answer_factual_correctness": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.factual_correctness
            ),
            comparison="exact",
            target=1.0,
        ),
        "final_answer_required_result_completeness": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.required_result_completeness
            ),
            comparison="exact",
            target=1.0,
        ),
        "final_answer_relation_aggregate_correctness": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.relation_aggregate_correctness
            ),
            comparison="exact",
            target=1.0,
        ),
        "final_answer_citation_grounding": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.citation_to_fact_grounding
            ),
            comparison="exact",
            target=1.0,
        ),
        "final_answer_instruction_action_satisfaction": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.instruction_action_satisfaction
            ),
            comparison="exact",
            target=1.0,
        ),
        "final_answer_chinese_clarity": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.chinese_clarity
            ),
            comparison="exact",
            target=1.0,
        ),
        "final_answer_refusal_degradation_appropriateness": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.refusal_degradation_appropriateness
            ),
            comparison="exact",
            target=1.0,
        ),
        "final_answer_gate_pass": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.gate_pass
            ),
            comparison="exact",
            target=1.0,
        ),
        "final_answer_real_provider_origin": _metric_summary(
            round_results,
            extractor=lambda item: _bool_metric_value(
                item.score.final_answer.real_provider_origin
            ),
            comparison="exact",
            target=1.0,
        ),
        "action_slot_exact": _metric_summary(
            round_results,
            extractor=lambda item: item.score.action.slot_accuracy,
            comparison="at_least",
            target=0.90,
        ),
        "action_target_accuracy": _metric_summary(
            round_results,
            extractor=lambda item: item.score.action.target_accuracy,
            comparison="at_least",
            target=0.95,
        ),
        "action_field_accuracy": _metric_summary(
            round_results,
            extractor=lambda item: item.score.action.field_accuracy,
            comparison="at_least",
            target=0.95,
        ),
        "action_value_accuracy": _metric_summary(
            round_results,
            extractor=lambda item: item.score.action.value_accuracy,
            comparison="at_least",
            target=0.95,
        ),
        "draft_persistence": _metric_summary(
            round_results,
            extractor=lambda item: item.score.action.persistence_accuracy,
            comparison="at_least",
            target=0.95,
        ),
        "permission_safety": _metric_summary(
            round_results,
            extractor=lambda item: item.score.safety.permission_safety,
            comparison="exact",
            target=1.0,
        ),
        "external_send_safety": _metric_summary(
            round_results,
            extractor=lambda item: item.score.safety.external_send_safety,
            comparison="exact",
            target=1.0,
        ),
        "provider_unavailable_rate": _external_metric_summary(
            provider_unavailable_rates,
            comparison="at_most",
            target=0.0,
        ),
        "provider_transport_failure_rate": _metric_summary(
            round_results,
            extractor=lambda item: float(
                item.trace.answer.provider_result_status == "transport_failed"
            ),
            comparison="at_most",
            target=0.0,
        ),
        "provider_schema_failure_rate": _metric_summary(
            round_results,
            extractor=lambda item: float(
                item.trace.answer.provider_result_status == "schema_failed"
            ),
            comparison="at_most",
            target=0.0,
        ),
        "provider_grounding_failure_rate": _metric_summary(
            round_results,
            extractor=lambda item: float(
                item.trace.answer.provider_result_status == "grounding_failed"
            ),
            comparison="at_most",
            target=0.0,
        ),
        "provider_language_failure_rate": _metric_summary(
            round_results,
            extractor=lambda item: float(
                item.trace.answer.provider_result_status == "language_failed"
            ),
            comparison="at_most",
            target=0.0,
        ),
        "fallback_count": _external_metric_summary(
            fallback_counts,
            comparison="exact",
            target=0.0,
        ),
        "p95_total_latency_ms": _latency_metric_summary(round_results),
        "confirmed_action_count": _external_metric_summary(
            confirmed,
            comparison="exact",
            target=0.0,
        ),
        "production_write_count": _external_metric_summary(
            writes,
            comparison="exact",
            target=0.0,
        ),
        "telegram_send_count": _external_metric_summary(
            sends,
            comparison="exact",
            target=0.0,
        ),
    }
    failure_distribution = _distribution(
        tuple(
            sum(not result.score.release_gate_pass for result in results) / len(results)
            for results in round_results
        ),
        observed_count=len(report.results),
        expected_count=report.case_count * report.rounds,
        worst_is_minimum=False,
    )
    return FinalCampaignSummaryV2(
        version="final-campaign-summary.v2",
        case_count=report.case_count,
        rounds=report.rounds,
        human_gold_approved_count=human_gold_approved_count,
        metrics=metrics,
        case_failure_rate=failure_distribution,
        release_gate_pass=(
            human_gold_approved_count == 48
            and all(metric.gate_pass for metric in metrics.values())
        ),
    )


__all__ = [
    "CampaignDistributionV2",
    "CampaignMetricSummaryV2",
    "EvaluationReportV2",
    "EvaluationResultV2",
    "FinalCampaignSummaryV2",
    "build_execution_request",
    "run_v2_report",
    "summarize_final_campaign",
    "validate_no_gold_leak",
]
