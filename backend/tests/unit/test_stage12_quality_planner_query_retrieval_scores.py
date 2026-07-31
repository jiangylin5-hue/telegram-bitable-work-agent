from __future__ import annotations

import pytest

from scripts.stage12_quality_evaluation import (
    ExpectedObjective,
    RuntimePlannerTrace,
    RuntimeQueryTrace,
    RuntimeRetrievalTrace,
    build_stage12_truth_cases,
    score_planner,
    score_query,
    score_retrieval,
)


def _case(case_id: str):
    return next(case for case in build_stage12_truth_cases() if case.case_id == case_id)


def _planner_trace(case_id: str) -> RuntimePlannerTrace:
    expected = _case(case_id).expected_task_spec
    return RuntimePlannerTrace(
        observation_status="observed",
        objectives=expected.objectives,
        dependency_edges=expected.dependency_edges,
        action_slots=expected.action_slots,
    )


def _query_trace(case_id: str) -> RuntimeQueryTrace:
    case = _case(case_id)
    expected = case.expected_query_result
    predicates = tuple(
        predicate
        for objective in case.expected_task_spec.objectives
        for predicate in objective.predicates
    )
    return RuntimeQueryTrace(
        observation_status="observed",
        result_record_ids=expected.required_result_records,
        evidence_record_ids=expected.allowed_evidence_records,
        predicates=predicates,
        relation_paths=expected.relation_paths,
        aggregates=expected.aggregates,
        facts=(),
        complete=True,
    )


def _retrieval_trace(case_id: str) -> RuntimeRetrievalTrace:
    expected = _case(case_id).expected_query_result
    relevant = expected.required_result_records + expected.allowed_evidence_records
    return RuntimeRetrievalTrace(
        observation_status="observed",
        candidate_record_ids=relevant,
        selected_evidence_record_ids=relevant,
        candidate_table_by_record={
            record_id: (
                "projects"
                if record_id.startswith("PRJ-")
                else "risks" if record_id.startswith("RISK-") else "work_items"
            )
            for record_id in relevant
        },
        relation_paths=expected.relation_paths,
        complete=True,
    )


def test_planner_exact_match_includes_dependency_dag_but_not_action_slots() -> None:
    case = _case("draft_01")
    trace = _planner_trace("draft_01").model_copy(update={"action_slots": ()})

    score = score_planner(case, trace)

    assert score.observation_status == "observed"
    assert score.objective_precision == 1.0
    assert score.objective_recall == 1.0
    assert score.objective_exact is True
    assert score.dependency_edge_exact is True
    assert score.predicate_exact is True
    assert score.gate_pass is True


def test_planner_extra_objective_loses_precision() -> None:
    case = _case("join_01")
    trace = _planner_trace("join_01")
    extra = ExpectedObjective(
        objective_id="obj-extra",
        kind="risk_analysis",
        required=True,
        entity_scope=("PRJ-ATLAS",),
        output_contract="risk_assessments",
        predicates=(),
        group_by=(),
        relation_paths=(),
    )

    score = score_planner(
        case,
        trace.model_copy(update={"objectives": trace.objectives + (extra,)}),
    )

    assert score.objective_precision == 0.5
    assert score.objective_recall == 1.0
    assert score.objective_exact is False
    assert score.gate_pass is False


def test_planner_missing_objective_and_edge_loses_recall() -> None:
    case = _case("risk_02")
    trace = _planner_trace("risk_02")

    score = score_planner(
        case,
        trace.model_copy(
            update={"objectives": trace.objectives[:1], "dependency_edges": ()}
        ),
    )

    assert score.objective_precision == 1.0
    assert score.objective_recall == 0.5
    assert score.dependency_edge_exact is False
    assert score.objective_exact is False


def test_planner_predicate_value_mismatch_is_independent() -> None:
    case = _case("risk_02")
    trace = _planner_trace("risk_02")
    fact = trace.objectives[0]
    wrong_predicate = fact.predicates[0].model_copy(update={"value": "medium"})
    wrong_fact = fact.model_copy(
        update={"predicates": (wrong_predicate,) + fact.predicates[1:]}
    )

    score = score_planner(
        case,
        trace.model_copy(update={"objectives": (wrong_fact,) + trace.objectives[1:]}),
    )

    assert score.objective_precision == 1.0
    assert score.objective_recall == 1.0
    assert score.predicate_exact is False
    assert score.gate_pass is False


def test_query_scores_filter_aggregate_and_join_path_independently() -> None:
    case = _case("join_08")
    trace = _query_trace("join_08")

    score = score_query(case, trace)

    assert score.filter_precision == 1.0
    assert score.filter_recall == 1.0
    assert score.filter_exact is True
    assert score.aggregate_exact is True
    assert score.join_path_exact is True
    assert score.forbidden_result_count == 0
    assert score.gate_pass is True


def test_query_wrong_typed_aggregate_and_forbidden_result_fail_gate() -> None:
    case = _case("risk_04")
    trace = _query_trace("risk_04")
    wrong_aggregate = trace.aggregates[0].model_copy(update={"value": "3"})
    forbidden = case.expected_query_result.forbidden_result_records[0]

    score = score_query(
        case,
        trace.model_copy(
            update={
                "result_record_ids": trace.result_record_ids + (forbidden,),
                "aggregates": (wrong_aggregate,) + trace.aggregates[1:],
            }
        ),
    )

    assert score.filter_exact is False
    assert score.aggregate_exact is False
    assert score.forbidden_result_count == 1
    assert score.gate_pass is False


def test_retrieval_uses_required_and_allowed_evidence_with_k_denominator() -> None:
    case = _case("join_02")
    trace = _retrieval_trace("join_02").model_copy(
        update={
            "candidate_record_ids": (
                "MT-004",
                "RISK-004",
                "PRJ-BEACON",
                "MT-999",
            ),
            "candidate_table_by_record": {
                "MT-004": "work_items",
                "RISK-004": "risks",
                "PRJ-BEACON": "projects",
                "MT-999": "work_items",
            },
        }
    )

    score = score_retrieval(case, trace, k=5)

    assert score.candidate_recall_at_k == 1.0
    assert score.candidate_precision_at_k == pytest.approx(0.6)
    assert score.per_table_recall == {
        "projects": 1.0,
        "risks": 1.0,
        "work_items": 1.0,
    }
    assert score.join_path_exact is True
    assert score.gate_pass is True


def test_retrieval_missing_table_candidate_is_visible() -> None:
    case = _case("join_02")
    trace = _retrieval_trace("join_02").model_copy(
        update={
            "candidate_record_ids": ("MT-004",),
            "candidate_table_by_record": {"MT-004": "work_items"},
        }
    )

    score = score_retrieval(case, trace, k=20)

    assert score.candidate_recall_at_k == pytest.approx(1 / 3)
    assert score.candidate_precision_at_k == pytest.approx(1 / 20)
    assert score.per_table_recall == {
        "projects": 0.0,
        "risks": 0.0,
        "work_items": 1.0,
    }
    assert score.gate_pass is False


def test_not_observed_metrics_remain_null_and_fail_release_gate() -> None:
    case = _case("join_02")
    query_trace = _query_trace("join_02").model_copy(
        update={"observation_status": "not_observed"}
    )
    retrieval_trace = _retrieval_trace("join_02").model_copy(
        update={"observation_status": "not_observed"}
    )

    planner = score_planner(case, None)
    query = score_query(case, query_trace)
    retrieval = score_retrieval(case, retrieval_trace)

    assert planner.objective_precision is None
    assert query.filter_precision is None
    assert retrieval.candidate_recall_at_k is None
    assert planner.gate_pass is False
    assert query.gate_pass is False
    assert retrieval.gate_pass is False


def test_structured_query_can_mark_embedding_retrieval_not_applicable() -> None:
    case = _case("join_08")
    trace = _retrieval_trace("join_08").model_copy(
        update={
            "observation_status": "not_applicable",
            "candidate_record_ids": (),
            "selected_evidence_record_ids": (),
            "candidate_table_by_record": {},
            "relation_paths": (),
            "complete": True,
        }
    )

    score = score_retrieval(case, trace)

    assert score.observation_status == "not_applicable"
    assert score.candidate_recall_at_k is None
    assert score.gate_pass is True
