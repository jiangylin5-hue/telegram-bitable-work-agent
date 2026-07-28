from scripts.stage09_real_table_quality_eval import (
    build_fixture_cases,
    load_fixture_rows,
    score_case_response,
    summarize_case_scores,
)


def test_fixture_cases_cover_exact_filter_aggregate_negative_and_guard_paths() -> None:
    cases = build_fixture_cases(load_fixture_rows())

    assert len(cases) == 10
    assert {case.kind for case in cases} == {
        "exact",
        "filter",
        "aggregate",
        "negative",
        "guard",
    }
    assert next(case for case in cases if case.case_id == "exact_eval_014").truth_codes == (
        "EVAL-014",
    )
    assert next(case for case in cases if case.case_id == "aggregate_done_count").truth_value == "6"


def test_score_case_response_counts_only_truth_citations_and_facts() -> None:
    cases = build_fixture_cases(load_fixture_rows())
    case = next(case for case in cases if case.case_id == "exact_eval_014")
    record_ids = {"row-14": "EVAL-014", "row-1": "EVAL-001"}

    score = score_case_response(
        case,
        {
            "answer": "EVAL-014 is blocked, high risk, and Fix structured answer contract.",
            "citations": [{"record_id": "row-14", "field_keys": ["ticket_code", "status", "risk_level", "summary"]}],
            "skill_evidence": {"selected_skills": [{"skill_id": "platform-base"}, {"skill_id": "platform-tabular-analysis"}]},
        },
        record_code_by_id=record_ids,
        allowed_field_keys={"ticket_code", "status", "risk_level", "summary"},
    )

    assert score.retrieval_recall_numerator == 1
    assert score.retrieval_recall_denominator == 1
    assert score.retrieval_precision_numerator == 1
    assert score.retrieval_precision_denominator == 1
    assert score.fact_correct is True
    assert score.citation_safe is True
    assert score.required_skills_hit is True
    assert score.unsupported_claim is False
    assert summarize_case_scores([score])["exact_match_accuracy"] == 1.0


def test_score_case_response_rejects_unrelated_citation_and_unsupported_ticket_claim() -> None:
    case = next(
        case
        for case in build_fixture_cases(load_fixture_rows())
        if case.case_id == "exact_eval_014"
    )

    score = score_case_response(
        case,
        {
            "answer": "EVAL-001 is blocked.",
            "citations": [{"record_id": "row-1", "field_keys": ["ticket_code", "status"]}],
            "skill_evidence": {"selected_skills": [{"skill_id": "platform-base"}]},
        },
        record_code_by_id={"row-14": "EVAL-014", "row-1": "EVAL-001"},
        allowed_field_keys={"ticket_code", "status", "risk_level", "summary"},
    )

    assert score.retrieval_recall_numerator == 0
    assert score.retrieval_precision_numerator == 0
    assert score.fact_correct is False
    assert score.citation_safe is True
    assert score.required_skills_hit is False
    assert score.unsupported_claim is True


def test_score_case_response_treats_separator_equivalent_scalar_as_factually_equal() -> None:
    cases = build_fixture_cases(load_fixture_rows())
    case = next(case for case in cases if case.case_id == "exact_eval_014")

    score = score_case_response(
        case,
        {
            "answer": "EVAL-014 is blocked, high risk, and Fix structured answer contract.",
            "citations": [{"record_id": "row-14", "field_keys": ["ticket_code"]}],
            "skill_evidence": {"selected_skills": [{"skill_id": "platform-base"}, {"skill_id": "platform-tabular-analysis"}]},
        },
        record_code_by_id={"row-14": "EVAL-014"},
        allowed_field_keys={"ticket_code"},
    )

    assert score.fact_correct is True
