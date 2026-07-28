from app.services.stage09_table_retrieval import (
    answer_covers_result_ticket_codes,
    execute_visible_table_query,
    parse_supported_table_query,
)


RECORDS = [
    {"id": "row-1", "fields": {"ticket_code": "EVAL-001", "status": "in_progress", "risk_level": "medium", "project": "Atlas"}},
    {"id": "row-2", "fields": {"ticket_code": "EVAL-002", "status": "blocked", "risk_level": "high", "priority": "high", "project": "Atlas"}},
    {"id": "row-3", "fields": {"ticket_code": "EVAL-003", "status": "blocked", "risk_level": "high", "project": "Beacon"}},
]


def test_exact_identifier_lookup_returns_only_the_matching_visible_record() -> None:
    intent = parse_supported_table_query("Show EVAL-002.", RECORDS)

    result = execute_visible_table_query(intent, RECORDS)

    assert result.mode == "records"
    assert result.record_ids == ("row-2",)
    assert result.records == (RECORDS[1],)


def test_conjunctive_visible_field_filter_returns_all_and_only_matches() -> None:
    intent = parse_supported_table_query("List blocked high risk work items.", RECORDS)

    result = execute_visible_table_query(intent, RECORDS)

    assert result.record_ids == ("row-2", "row-3")


def test_field_qualified_value_does_not_become_a_filter_for_another_field() -> None:
    records = [
        *RECORDS,
        {
            "id": "row-4",
            "fields": {
                "ticket_code": "EVAL-004",
                "status": "blocked",
                "risk_level": "high",
                "priority": "medium",
                "project": "Cedar",
            },
        },
    ]

    intent = parse_supported_table_query("List blocked high risk work items.", records)

    result = execute_visible_table_query(intent, records)

    assert result.record_ids == ("row-2", "row-3", "row-4")


def test_count_query_returns_count_and_supporting_records() -> None:
    intent = parse_supported_table_query("How many work items are blocked?", RECORDS)

    result = execute_visible_table_query(intent, RECORDS)

    assert result.mode == "count"
    assert result.aggregate_value == 2
    assert result.record_ids == ("row-2", "row-3")


def test_separator_equivalent_prompt_value_matches_canonical_stored_scalar() -> None:
    intent = parse_supported_table_query("List Atlas work items in progress.", RECORDS)

    result = execute_visible_table_query(intent, RECORDS)

    assert result.record_ids == ("row-1",)


def test_record_explanation_must_name_each_ticket_code_in_result_set() -> None:
    assert answer_covers_result_ticket_codes("EVAL-001 and EVAL-002 are blocked.", RECORDS[:2])
    assert not answer_covers_result_ticket_codes("EVAL-001 is blocked.", RECORDS[:2])


def test_chinese_query_aliases_map_to_bounded_visible_filters_and_count() -> None:
    records = [
        *RECORDS,
        {"id": "row-4", "fields": {"ticket_code": "EVAL-004", "status": "done", "risk_level": "low", "priority": "high", "project": "Atlas"}},
    ]

    list_intent = parse_supported_table_query("列出 Atlas 中进行中的工作项", records)
    count_intent = parse_supported_table_query("有多少个已阻塞的工作项", records)

    assert execute_visible_table_query(list_intent, records).record_ids == ("row-1",)
    assert execute_visible_table_query(count_intent, records).aggregate_value == 2


def test_unknown_or_hidden_field_query_requires_clarification() -> None:
    assert parse_supported_table_query("Show private_notes for EVAL-002.", RECORDS) is None
    assert parse_supported_table_query("Which work items need attention?", RECORDS) is None
