from app.services.permissions import Actor
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from scripts.stage09_multitable_chinese_eval import (
    build_chinese_cases,
    build_multitable_fixture,
    verify_multitable_fixture,
)


def test_imports_three_csv_tables_and_creates_same_base_relation_edges() -> None:
    actor = Actor(actor_type="user", actor_id="stage09-multitable-owner", role="owner")
    fixture = build_multitable_fixture(InMemoryStage06PlatformUnitOfWork(), actor)

    assert verify_multitable_fixture(fixture) == {
        "table_count": 3,
        "record_count": 32,
        "relation_field_count": 2,
        "edge_count": 26,
    }
    assert fixture.work_item_project_record_ids["MT-001"] == fixture.project_record_ids["PRJ-ATLAS"]
    assert fixture.risk_work_item_record_ids["RISK-001"] == fixture.work_item_record_ids["MT-001"]


def test_builds_twenty_chinese_centric_cases_with_all_required_query_kinds() -> None:
    actor = Actor(actor_type="user", actor_id="stage09-multitable-owner", role="owner")
    fixture = build_multitable_fixture(InMemoryStage06PlatformUnitOfWork(), actor)

    cases = build_chinese_cases(fixture)

    assert len(cases) == 20
    assert sum(any("一" <= character <= "龥" for character in case.prompt) for case in cases) >= 12
    assert {case.kind for case in cases} >= {"exact", "filter", "aggregate", "negative", "guard"}
    assert all(case.required_skill_ids for case in cases)
