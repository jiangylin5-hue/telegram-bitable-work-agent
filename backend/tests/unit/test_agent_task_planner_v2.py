from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from app.schemas.agent_task_spec_v2 import (
    AuthorizedEntitySpec,
    AuthorizedFieldSpec,
    AuthorizedSchemaSnapshot,
    AuthorizedTableSpec,
    PlannerRequestV2,
    authorized_schema_sha256,
)
from app.services.agent_task_planner_v2 import (
    PlannerAmbiguityDecision,
    PlannerAmbiguityRequest,
    plan_task_v2,
)


WORKSPACE_ID = UUID("10000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = UUID("10000000-0000-4000-8000-000000000002")
BASE_ID = UUID("10000000-0000-4000-8000-000000000003")
PROJECTS_ID = UUID("10000000-0000-4000-8000-000000000004")
WORK_ITEMS_ID = UUID("10000000-0000-4000-8000-000000000005")
TASKS_ID = UUID("10000000-0000-4000-8000-000000000006")


def _field(
    table_id: UUID,
    suffix: int,
    key: str,
    name: str,
    field_type: str,
    *,
    choices: tuple[str, ...] = (),
    writable: bool = True,
    default_value=None,
    linked_target_table_id: UUID | None = None,
):
    return AuthorizedFieldSpec(
        field_id=UUID(f"10000000-0000-4000-8000-{suffix:012d}"),
        table_id=table_id,
        key=key,
        name=name,
        field_type=field_type,
        aliases=(),
        choices=choices,
        writable=writable,
        default_value=default_value,
        linked_target_table_id=linked_target_table_id,
    )


def _snapshot() -> AuthorizedSchemaSnapshot:
    tables = (
        AuthorizedTableSpec(
            table_id=PROJECTS_ID,
            base_id=BASE_ID,
            key="projects",
            name="项目",
            aliases=("项目表",),
            fields=(
                _field(PROJECTS_ID, 101, "project_code", "项目编号", "text"),
                _field(
                    PROJECTS_ID,
                    102,
                    "delivery_state",
                    "交付状态",
                    "status",
                    choices=("active", "paused"),
                ),
            ),
        ),
        AuthorizedTableSpec(
            table_id=WORK_ITEMS_ID,
            base_id=BASE_ID,
            key="work_items",
            name="工作项",
            aliases=("事项",),
            fields=(
                _field(WORK_ITEMS_ID, 201, "ticket_code", "事项编号", "text"),
                _field(
                    WORK_ITEMS_ID,
                    202,
                    "status",
                    "状态",
                    "status",
                    choices=("planned", "in_progress", "done", "blocked"),
                ),
                _field(
                    WORK_ITEMS_ID,
                    203,
                    "priority",
                    "优先级",
                    "single_select",
                    choices=("high", "medium", "low"),
                ),
                _field(
                    WORK_ITEMS_ID,
                    204,
                    "blocked_reason",
                    "阻塞原因",
                    "text",
                    writable=False,
                ),
                _field(WORK_ITEMS_ID, 205, "title", "标题", "text"),
                _field(
                    WORK_ITEMS_ID,
                    206,
                    "project_link",
                    "关联项目",
                    "linked_record",
                    linked_target_table_id=PROJECTS_ID,
                ),
                _field(WORK_ITEMS_ID, 207, "risk_level", "风险级别", "text"),
            ),
        ),
        AuthorizedTableSpec(
            table_id=TASKS_ID,
            base_id=BASE_ID,
            key="tasks",
            name="任务",
            aliases=("任务表",),
            fields=(
                _field(TASKS_ID, 301, "title", "标题", "text"),
                _field(
                    TASKS_ID,
                    302,
                    "status",
                    "状态",
                    "status",
                    choices=("planned", "done"),
                    default_value="planned",
                ),
                _field(TASKS_ID, 303, "due_date", "截止日期", "date"),
                _field(
                    TASKS_ID,
                    304,
                    "source_work_item",
                    "来源工作项",
                    "linked_record",
                    linked_target_table_id=WORK_ITEMS_ID,
                ),
                _field(
                    TASKS_ID,
                    305,
                    "priority",
                    "优先级",
                    "single_select",
                    choices=("high", "medium", "low"),
                    default_value="medium",
                ),
                _field(
                    TASKS_ID,
                    306,
                    "project_link",
                    "关联项目",
                    "linked_record",
                    linked_target_table_id=PROJECTS_ID,
                ),
                _field(TASKS_ID, 307, "assignee", "负责人", "linked_record"),
            ),
        ),
    )
    values = {
        "version": "authorized-schema-snapshot.v1",
        "workspace_id": WORKSPACE_ID,
        "employee_id": EMPLOYEE_ID,
        "scope_hash": "a" * 64,
        "tables": tables,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _entities() -> tuple[AuthorizedEntitySpec, ...]:
    return (
        AuthorizedEntitySpec(
            entity_id=UUID("10000000-0000-4000-8000-000000001001"),
            table_id=PROJECTS_ID,
            code="PRJ-ATLAS",
            label="Atlas",
            aliases=(),
        ),
        AuthorizedEntitySpec(
            entity_id=UUID("10000000-0000-4000-8000-000000001002"),
            table_id=PROJECTS_ID,
            code="PRJ-BEACON",
            label="Beacon",
            aliases=(),
        ),
        AuthorizedEntitySpec(
            entity_id=UUID("10000000-0000-4000-8000-000000002017"),
            table_id=WORK_ITEMS_ID,
            code="MT-017",
            label="Fjord rollback",
            aliases=(),
        ),
        AuthorizedEntitySpec(
            entity_id=UUID("10000000-0000-4000-8000-000000002001"),
            table_id=WORK_ITEMS_ID,
            code="MT-001",
            label="Atlas launch checklist",
            aliases=(),
        ),
        AuthorizedEntitySpec(
            entity_id=UUID("10000000-0000-4000-8000-000000002004"),
            table_id=WORK_ITEMS_ID,
            code="MT-004",
            label="Beacon API dependency",
            aliases=(),
        ),
    )


def _request(
    query: str,
    *,
    allowed_actions: tuple[str, ...] | None = None,
    snapshot: AuthorizedSchemaSnapshot | None = None,
    entities: tuple[AuthorizedEntitySpec, ...] | None = None,
    clock: datetime | None = None,
) -> PlannerRequestV2:
    return PlannerRequestV2(
        query=query,
        authorized_schema=snapshot or _snapshot(),
        authorized_entities=_entities() if entities is None else entities,
        clock=clock or datetime.fromisoformat("2026-07-29T00:00:00+08:00"),
        timezone_name="Asia/Shanghai",
        allowed_action_kinds=allowed_actions
        or ("record.create", "record.update", "task.create", "reminder.request"),
    )


def _snapshot_with_tables(
    snapshot: AuthorizedSchemaSnapshot,
    tables: tuple[AuthorizedTableSpec, ...],
) -> AuthorizedSchemaSnapshot:
    values = {
        "version": snapshot.version,
        "workspace_id": snapshot.workspace_id,
        "employee_id": snapshot.employee_id,
        "scope_hash": snapshot.scope_hash,
        "tables": tables,
    }
    return AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )


def _plan(query: str, *, allowed_actions: tuple[str, ...] | None = None):
    return plan_task_v2(_request(query, allowed_actions=allowed_actions)).task_spec


@pytest.mark.parametrize(
    "query",
    (
        "列出 high 优先级未完成事项",
        "显示 blocked_reason",
        "查看 blocked 工作项",
    ),
)
def test_field_values_do_not_create_risk_objective(query: str) -> None:
    spec = _plan(query)

    assert [item.kind for item in spec.objectives] == ["fact_query"]
    assert spec.action_slots == ()


def test_review_task_phrase_creates_one_task_without_risk() -> None:
    spec = _plan("创建回滚方案评审任务")

    assert [item.kind for item in spec.objectives] == [
        "fact_query",
        "task_creation",
    ]
    assert [item.action_kind for item in spec.action_slots] == ["task.create"]
    assert spec.action_slots[0].target.table_id == TASKS_ID


def test_task_source_relation_uses_table_identity_instead_of_code_prefix() -> None:
    payload = _snapshot().model_dump(mode="python")
    for table in payload["tables"]:
        for field in table["fields"]:
            if field["key"] == "project_link":
                field["linked_target_table_id"] = PROJECTS_ID
            elif field["key"] == "source_work_item":
                field["linked_target_table_id"] = WORK_ITEMS_ID
    payload["schema_hash"] = authorized_schema_sha256(
        version=payload["version"],
        workspace_id=payload["workspace_id"],
        employee_id=payload["employee_id"],
        scope_hash=payload["scope_hash"],
        tables=tuple(
            AuthorizedTableSpec.model_validate(item) for item in payload["tables"]
        ),
    )
    try:
        snapshot = AuthorizedSchemaSnapshot.model_validate(payload)
    except Exception as exc:
        pytest.fail(f"linked relation target metadata is missing: {exc}")
    entity = AuthorizedEntitySpec(
        entity_id=UUID("10000000-0000-4000-8000-000000009999"),
        table_id=PROJECTS_ID,
        code="CASE-42",
        label="Apollo",
        aliases=(),
    )

    spec = plan_task_v2(
        _request(
            "为 CASE-42 创建高优先级范围确认任务",
            snapshot=snapshot,
            entities=(entity,),
        )
    ).task_spec

    slot = next(item for item in spec.action_slots if item.action_kind == "task.create")
    assignments = {item.field_key: item.value for item in slot.assignments}
    assert assignments["project_link"] == ["CASE-42"]


def test_explicit_risk_comparison_depends_on_fact_objective() -> None:
    spec = _plan("比较 Atlas 和 Beacon 的风险并解释原因")
    by_kind = {item.kind: item for item in spec.objectives}

    assert set(by_kind) == {"fact_query", "risk_analysis"}
    assert [
        (edge.from_objective_id, edge.to_objective_id) for edge in spec.dependency_edges
    ] == [(by_kind["fact_query"].objective_id, by_kind["risk_analysis"].objective_id)]
    assert by_kind["risk_analysis"].entity_codes == ("PRJ-ATLAS", "PRJ-BEACON")


@pytest.mark.parametrize(
    "query",
    (
        "找出有 high 风险但工作项状态不是 blocked 的事项。",
        "按风险级别汇总开放风险数量，并列出支撑记录编号。",
        "汇总今日阻塞项，按风险排序，生成管理日报。",
        "列出所有 blocked 且 high 风险的工作项，按项目分组。",
    ),
)
def test_analytical_risk_requests_create_one_risk_objective(query: str) -> None:
    spec = _plan(query)

    assert [item.kind for item in spec.objectives].count("risk_analysis") == 1


def test_action_risk_justification_does_not_create_standalone_analysis() -> None:
    spec = _plan("将 MT-017 的 priority 提议调整为 high，并解释风险依据。")

    assert [item.kind for item in spec.objectives] == [
        "fact_query",
        "record_change",
    ]


def test_each_explicit_entity_gets_an_independent_task_slot() -> None:
    spec = _plan("为 Atlas 和 Beacon 分别创建一个跟进任务草稿")

    task_objectives = [item for item in spec.objectives if item.kind == "task_creation"]
    assert len(task_objectives) == 1
    assert len(spec.action_slots) == 2
    assert {slot.target.source_entity_codes for slot in spec.action_slots} == {
        ("PRJ-ATLAS",),
        ("PRJ-BEACON",),
    }
    assert {slot.objective_id for slot in spec.action_slots} == {
        task_objectives[0].objective_id
    }


def test_restricted_write_without_read_has_no_synthetic_fact_objective() -> None:
    spec = _plan("把无权编辑的 MT-001 internal_note 改为已处理。")

    assert [item.kind for item in spec.objectives] == [
        "restricted_request",
        "record_change",
    ]


def test_outside_scope_query_preserves_denied_fact_risk_and_task_intents() -> None:
    spec = _plan("查询当前 workspace 之外项目的风险并生成任务。")

    assert [item.kind for item in spec.objectives] == [
        "restricted_request",
        "fact_query",
        "risk_analysis",
        "task_creation",
    ]
    by_kind = {item.kind: item for item in spec.objectives}
    assert {item.planning_outcome for item in by_kind.values()} == {"denied"}
    restricted_id = by_kind["restricted_request"].objective_id
    assert {
        (edge.from_objective_id, edge.to_objective_id) for edge in spec.dependency_edges
    } == {
        (restricted_id, by_kind["fact_query"].objective_id),
        (restricted_id, by_kind["risk_analysis"].objective_id),
        (restricted_id, by_kind["task_creation"].objective_id),
    }


def test_conflicted_update_is_denied_but_independent_task_continues() -> None:
    spec = _plan("把 MT-017 同时改为 done 和 blocked，并创建明天之前的评审任务")
    update = next(
        item for item in spec.action_slots if item.action_kind == "record.update"
    )
    task = next(item for item in spec.action_slots if item.action_kind == "task.create")

    assert update.planning_outcome == "denied"
    assert update.denial_reason == "conflicting_assignments"
    assert update.conflict_group_id is not None
    assert task.planning_outcome == "planned"
    assert task.deadline_end_utc.isoformat() == "2026-07-30T16:00:00+00:00"
    assignments = {item.field_key: item.value for item in task.assignments}
    assert assignments["due_date"] == "2026-07-30"
    assert [item.kind for item in spec.objectives].count("conflict_resolution") == 1
    assert spec.conflict_groups[0].assignments[0].values == ("done", "blocked")


def test_action_value_ambiguity_does_not_block_exact_entity_fact_query() -> None:
    snapshot = _snapshot()
    tables = tuple(
        table.model_copy(
            update={
                "fields": tuple(
                    (
                        field.model_copy(update={"writable": False})
                        if table.table_id == WORK_ITEMS_ID and field.key == "status"
                        else field
                    )
                    for field in table.fields
                )
            }
        )
        for table in snapshot.tables
    )
    values = snapshot.model_dump(mode="python", exclude={"schema_hash"})
    values["tables"] = tables
    partial_snapshot = AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )

    spec = plan_task_v2(
        _request(
            "把 MT-017 同时改为 done 和 blocked，并创建明天之前的评审任务",
            snapshot=partial_snapshot,
        )
    ).task_spec

    fact = next(item for item in spec.objectives if item.kind == "fact_query")
    assert fact.planning_outcome == "planned"
    assert fact.denial_reason is None
    assert spec.query_intents[0].predicates == ()


def test_restricted_request_denies_only_its_objective() -> None:
    spec = _plan("汇总可见项目，同时读取客户密钥；合法部分继续")
    by_kind = {item.kind: item for item in spec.objectives}

    assert by_kind["fact_query"].planning_outcome == "planned"
    assert by_kind["restricted_request"].planning_outcome == "denied"
    assert (
        by_kind["restricted_request"].denial_reason == "field_not_in_authorized_schema"
    )


def test_field_permission_denial_does_not_block_independent_task() -> None:
    spec = _plan("把 MT-017 的 blocked_reason 更新为 waiting，并创建跟进任务")
    update = next(
        item for item in spec.action_slots if item.action_kind == "record.update"
    )
    task = next(item for item in spec.action_slots if item.action_kind == "task.create")

    assert update.planning_outcome == "denied"
    assert update.denial_reason == "field_permission_denied"
    assert task.planning_outcome == "planned"


def test_action_kind_outside_authorized_set_is_locally_denied() -> None:
    spec = _plan("为 Atlas 创建跟进任务", allowed_actions=("record.update",))
    slot = spec.action_slots[0]

    assert slot.action_kind == "task.create"
    assert slot.planning_outcome == "denied"
    assert slot.denial_reason == "action_kind_not_authorized"


def test_plan_is_hash_stable_and_counts_match_contract() -> None:
    first = _plan("为 Atlas 创建明天之前的评审任务")
    second = _plan("为 Atlas 创建明天之前的评审任务")

    assert first == second
    assert first.cost.objective_count == len(first.objectives)
    assert first.cost.action_slot_count == len(first.action_slots)
    assert first.provider_call_count == 0


def test_action_objectives_use_the_stable_controlled_proposal_contract() -> None:
    update_spec = _plan("把 MT-017 的 status 改为 done")
    task_spec = _plan("为 Atlas 创建跟进任务")

    update = next(
        item for item in update_spec.objectives if item.kind == "record_change"
    )
    task = next(item for item in task_spec.objectives if item.kind == "task_creation")
    assert update.output_contract == "controlled_action_proposal"
    assert task.output_contract == "controlled_action_proposal"


def test_task_slot_projects_defaults_and_authorized_project_relation() -> None:
    spec = _plan("为 PRJ-ATLAS 创建高优先级范围确认任务并指派项目负责人")
    slot = spec.action_slots[0]

    assert slot.action_kind == "task.create"
    assert set(slot.required_field_keys) == {
        "title",
        "project_link",
        "assignee",
        "priority",
        "status",
    }
    assert {item.field_key for item in slot.assignments} == set(
        slot.required_field_keys
    )
    assert slot.target.source_entity_codes == ("PRJ-ATLAS",)


def test_task_slot_uses_source_work_item_and_deterministic_due_date() -> None:
    spec = _plan("针对 MT-004 生成接口依赖跟进任务，今天处理")
    slot = spec.action_slots[0]

    assert set(slot.required_field_keys) == {
        "title",
        "source_work_item",
        "due_date",
        "priority",
        "status",
    }
    values = {item.field_key: item.value for item in slot.assignments}
    assert values["source_work_item"] == ["MT-004"]
    assert values["due_date"] == "2026-07-29"


def test_due_date_uses_workspace_timezone_when_runtime_clock_is_utc() -> None:
    utc_clock = datetime.fromisoformat("2026-07-28T16:00:00+00:00")
    today = plan_task_v2(
        _request(
            "针对 MT-004 生成接口依赖跟进任务，今天处理",
            clock=utc_clock,
        )
    ).task_spec.action_slots[0]
    tomorrow = plan_task_v2(
        _request("为 MT-017 创建明天之前的评审任务", clock=utc_clock)
    ).task_spec.action_slots[0]

    today_values = {item.field_key: item.value for item in today.assignments}
    tomorrow_values = {item.field_key: item.value for item in tomorrow.assignments}
    assert today_values["due_date"] == "2026-07-29"
    assert tomorrow_values["due_date"] == "2026-07-30"
    assert tomorrow.deadline_end_utc.isoformat() == "2026-07-30T16:00:00+00:00"


def test_record_create_slot_extracts_static_assignments_without_scanning_records() -> (
    None
):
    spec = _plan(
        "新增一条 Atlas 回归检查事项，状态 planned、优先级 high，只生成待确认草稿"
    )
    slot = next(
        item for item in spec.action_slots if item.action_kind == "record.create"
    )

    assert set(slot.required_field_keys) == {
        "title",
        "project_link",
        "status",
        "priority",
    }
    assert {item.field_key for item in slot.assignments} == set(
        slot.required_field_keys
    )
    assert slot.target.table_id == WORK_ITEMS_ID
    assert slot.target.source_entity_codes == ("PRJ-ATLAS",)


def test_draft_wording_still_produces_one_record_update_slot() -> None:
    spec = _plan("为 MT-012 补充 blocked_reason 为依赖未交付，只生成草稿")

    assert [item.action_kind for item in spec.action_slots] == ["record.update"]
    slot = spec.action_slots[0]
    assert slot.required_field_keys == ("blocked_reason",)
    assert slot.planning_outcome == "denied"
    assert slot.denial_reason == "field_permission_denied"


def test_task_draft_wording_does_not_duplicate_the_task_action() -> None:
    spec = _plan("针对 MT-004 生成接口依赖跟进任务，今天处理，只生成任务草稿")

    assert [item.action_kind for item in spec.action_slots] == ["task.create"]


def test_error_update_noun_does_not_create_a_second_update_action() -> None:
    spec = _plan(
        "把 MT-017 同时改为 done 和 blocked，并创建明天之前的评审任务；"
        "先识别冲突，不要生成错误更新"
    )

    assert [item.action_kind for item in spec.action_slots].count("record.update") == 1
    assert [item.action_kind for item in spec.action_slots].count("task.create") == 1


def test_direct_reminder_language_produces_a_bounded_reminder_slot() -> None:
    spec = _plan("提醒 MT-001 的负责人今天反馈阻塞原因，不要直接发送")

    assert [item.action_kind for item in spec.action_slots] == ["reminder.request"]
    slot = spec.action_slots[0]
    assert slot.target.source_entity_codes == ("MT-001",)
    assert slot.planning_outcome == "planned"


def test_collection_reminder_is_one_deferred_query_expansion_template() -> None:
    spec = _plan("为所有 high 且 blocked 事项生成负责人提醒请求，不能群发")

    assert [item.action_kind for item in spec.action_slots] == ["reminder.request"]
    slot = spec.action_slots[0]
    assert slot.planning_outcome == "planned"
    assert slot.target.table_id == spec.query_intents[0].root_table_id
    assert slot.target.record_codes == ()
    assert slot.target.source_entity_codes == ()
    assert slot.target.query_spec_ref == "query-intent:query-01"
    assert slot.target.expansion_policy == "each_distinct_owner"
    assert slot.target.resolution_status == "deferred_query_result"


@pytest.mark.parametrize(
    ("query", "expected"),
    (
        (
            "列出 blocked 且 high 风险的工作项",
            {("status", "eq", "blocked"), ("risk_level", "eq", "high")},
        ),
        (
            "找出 high 风险但工作项状态不是 blocked 的事项",
            {("risk_level", "eq", "high"), ("status", "ne", "blocked")},
        ),
        (
            "列出高优先级且未完成的工作项",
            {("priority", "eq", "high"), ("status", "ne", "done")},
        ),
        (
            "找出风险级别 high 但优先级不是 high 的工作项",
            {("risk_level", "eq", "high"), ("priority", "ne", "high")},
        ),
    ),
)
def test_static_query_phrases_produce_typed_predicates(
    query: str,
    expected: set[tuple[str, str, str]],
) -> None:
    spec = _plan(query)

    assert {
        (item.field_key, item.operator, str(item.value))
        for item in spec.query_intents[0].predicates
    } == expected


def test_action_assignment_enum_is_not_reused_as_query_predicate() -> None:
    spec = _plan("把 MT-017 的 status 改为 done")

    assert spec.query_intents[0].predicates == ()


def test_embedded_enum_word_in_field_key_is_not_a_predicate() -> None:
    spec = _plan("为 MT-017 补充 blocked_reason 为依赖未交付")

    assert spec.query_intents[0].predicates == ()


def test_proposed_adjustment_is_one_update_action_not_a_query_filter() -> None:
    spec = _plan("将 MT-017 的 priority 提议调整为 high，并解释风险依据")

    assert [item.action_kind for item in spec.action_slots] == ["record.update"]
    assert spec.query_intents[0].predicates == ()
    assert spec.action_slots[0].required_field_keys == ("priority",)


def test_project_traversal_keeps_static_project_identity_predicate() -> None:
    spec = _plan("列出 Atlas 项目下高优先级且未完成的工作项")

    assert {
        (item.field_key, item.operator, str(item.value))
        for item in spec.query_intents[0].predicates
    } == {
        ("project_code", "eq", "PRJ-ATLAS"),
        ("priority", "eq", "high"),
        ("status", "ne", "done"),
    }


def test_related_table_requirements_are_explicit_join_intents() -> None:
    spec = _plan("列出 Atlas 项目下高优先级且未完成的工作项")
    intent = spec.query_intents[0]

    assert intent.root_table_id == PROJECTS_ID
    assert [
        (
            item.target_table_id,
            item.purpose,
            item.requirement,
        )
        for item in intent.execution_spec.join_intents
    ] == [(WORK_ITEMS_ID, "filter", "required")]


def test_exact_entity_code_ownership_precedes_related_table_root_selection() -> None:
    spec = _plan("从 MT-017 反查所属项目")
    intent = spec.query_intents[0]

    assert intent.root_table_id == WORK_ITEMS_ID
    assert [item.target_table_id for item in intent.execution_spec.join_intents] == [
        PROJECTS_ID
    ]


def test_entity_project_relation_is_explicitly_projected() -> None:
    spec = _plan("查询 MT-017 的项目和风险。")
    intent = spec.query_intents[0]

    assert UUID("10000000-0000-4000-8000-000000000101") in (
        intent.execution_spec.projection_field_ids
    )


def test_three_status_phrase_emits_only_the_complete_in_predicate() -> None:
    spec = _plan("列出进行中、计划中和已完成事项")

    assert [
        (item.field_key, item.operator, item.value)
        for item in spec.query_intents[0].predicates
    ] == [("status", "in", ["in_progress", "planned", "done"])]


def test_independent_aggregate_and_risk_code_clauses_get_separate_fact_intents() -> (
    None
):
    spec = _plan("按项目汇总未完成工作项数量，并列出每个项目的风险编号")

    assert [item.output_contract for item in spec.objectives] == [
        "unfinished_work_item_aggregates",
        "project_risk_codes",
    ]
    assert [item.query_spec_ref for item in spec.objectives] == [
        "query-intent:query-01",
        "query-intent:query-02",
    ]
    assert len(spec.query_intents) == 2
    aggregate = spec.query_intents[0].execution_spec.aggregations[0]
    assert [
        (item.field_key, item.operator, item.value)
        for item in spec.query_intents[0].predicates
    ] == [("status", "ne", "done")]
    assert aggregate.output_key == "unfinished_work_items"
    assert aggregate.filter_expression.predicate.field_key == "status"
    assert aggregate.filter_expression.predicate.operator == "ne"
    assert aggregate.filter_expression.predicate.value == "done"
    assert spec.query_intents[1].predicates == ()


def test_project_brief_is_a_daily_summary() -> None:
    spec = _plan("生成交付阶段项目简报")

    assert [item.kind for item in spec.objectives] == ["fact_query", "daily_summary"]


def test_explicit_risk_input_precedes_daily_summary() -> None:
    spec = _plan("生成暂停项目专项日报，说明事实、风险和下一步建议")
    by_kind = {item.kind: item.objective_id for item in spec.objectives}

    assert {
        (item.from_objective_id, item.to_objective_id, item.required)
        for item in spec.dependency_edges
    } == {
        (by_kind["fact_query"], by_kind["risk_analysis"], True),
        (by_kind["fact_query"], by_kind["daily_summary"], True),
        (by_kind["risk_analysis"], by_kind["daily_summary"], True),
    }


def test_optional_risk_failure_marks_only_the_risk_dependency_optional() -> None:
    spec = _plan("汇总 Atlas 风险；如果可选风险分析暂时失败，返回可验证的表格事实")

    assert len(spec.dependency_edges) == 1
    assert spec.dependency_edges[0].required is False


def test_reminder_safety_phrase_does_not_duplicate_the_reminder_action() -> None:
    spec = _plan("提醒 Fjord 负责人评审 MT-017，但只创建提醒请求")

    assert [item.action_kind for item in spec.action_slots] == ["reminder.request"]
    assert spec.action_slots[0].target.source_entity_codes == ("MT-017",)


def test_reminder_target_does_not_mix_entities_from_different_tables() -> None:
    entities = (
        *_entities(),
        AuthorizedEntitySpec(
            entity_id=UUID("10000000-0000-4000-8000-000000001017"),
            table_id=PROJECTS_ID,
            code="PRJ-FJORD",
            label="Fjord",
            aliases=(),
        ),
    )

    spec = plan_task_v2(
        _request(
            "提醒 Fjord 负责人评审 MT-017，但只创建提醒请求",
            entities=entities,
        )
    ).task_spec

    target = spec.action_slots[0].target
    assert target.table_id == WORK_ITEMS_ID
    assert target.source_entity_codes == ("MT-017",)


def test_each_project_creates_one_static_task_slot_per_authorized_project() -> None:
    spec = _plan("为 Atlas 和 Beacon 的每个项目生成一个跟进任务草稿")

    assert [item.target.source_entity_codes for item in spec.action_slots] == [
        ("PRJ-ATLAS",),
        ("PRJ-BEACON",),
    ]


def test_risk_level_choice_does_not_become_record_priority() -> None:
    spec = _plan("新增一条 Beacon 风险复核事项，关联项目并设为 medium 风险")
    slot = spec.action_slots[0]

    assert "risk_level" in slot.required_field_keys
    assert "priority" not in slot.required_field_keys


def test_user_declared_hidden_field_update_is_locally_denied() -> None:
    spec = _plan("把无权编辑的 MT-001 internal_note 改为已处理")
    slot = spec.action_slots[0]

    assert "restricted_request" in {item.kind for item in spec.objectives}
    assert slot.required_field_keys == ("internal_note",)
    assert slot.planning_outcome == "denied"
    assert slot.denial_reason == "field_permission_denied"


def test_outside_workspace_task_is_locally_denied_without_assignments() -> None:
    spec = _plan("查询当前 workspace 之外项目的风险并生成任务")
    slot = spec.action_slots[0]

    assert "restricted_request" in {item.kind for item in spec.objectives}
    assert slot.assignments == ()
    assert slot.required_field_keys == ()
    assert slot.planning_outcome == "denied"
    assert slot.denial_reason == "outside_workspace_scope_denied"


def test_highest_risk_task_is_a_deferred_result_template() -> None:
    spec = _plan("为最高风险项创建跟进任务草稿")
    target = spec.action_slots[0].target

    assert target.query_spec_ref == "query-intent:query-01"
    assert target.expansion_policy == "each_result"
    assert target.resolution_status == "deferred_query_result"


def test_filtered_risk_reminder_is_a_deferred_owner_template() -> None:
    spec = _plan("为 high 风险项生成提醒请求，绝不能直接发送")
    target = spec.action_slots[0].target

    assert target.query_spec_ref == "query-intent:query-01"
    assert target.expansion_policy == "each_distinct_owner"
    assert target.resolution_status == "deferred_query_result"


def test_update_draft_before_task_keeps_source_action_order() -> None:
    spec = _plan("把 MT-012 的 blocked_reason 生成更新草稿，并创建依赖跟进任务")

    assert [item.action_kind for item in spec.action_slots] == [
        "record.update",
        "task.create",
    ]


@pytest.mark.parametrize(
    "query",
    (
        "列出 Atlas 项目下高优先级且未完成的工作项，并给出关联风险。",
        "Beacon 项目有哪些阻塞工作项？对应开放风险编号是什么？",
        "生成 Atlas 和 Beacon 的项目日报，必须包含风险和阻塞依据。",
    ),
)
def test_risk_records_or_daily_evidence_do_not_imply_risk_analysis(
    query: str,
) -> None:
    spec = _plan(query)

    assert "risk_analysis" not in {item.kind for item in spec.objectives}


def test_exact_binding_never_calls_ambiguity_resolver() -> None:
    def fail_if_called(_request: PlannerAmbiguityRequest) -> PlannerAmbiguityDecision:
        raise AssertionError("resolver must not run for an exact unambiguous field")

    spec = plan_task_v2(
        _request("显示 work_items 的 priority"),
        ambiguity_resolver=fail_if_called,
    ).task_spec

    assert spec.provider_call_count == 0
    assert spec.objectives[0].planning_outcome == "planned"


def test_ambiguous_binding_calls_resolver_once_with_enumerated_candidates() -> None:
    calls: list[PlannerAmbiguityRequest] = []

    def resolve(request: PlannerAmbiguityRequest) -> PlannerAmbiguityDecision:
        calls.append(request)
        return PlannerAmbiguityDecision(
            mention_id=request.mention_id,
            selected_candidate_ids=(request.candidate_ids[0],),
        )

    spec = plan_task_v2(
        _request("显示 status"),
        ambiguity_resolver=resolve,
    ).task_spec

    assert len(calls) == 1
    assert calls[0].allowed_selection_count == 1
    assert len(calls[0].candidate_ids) == 2
    assert spec.provider_call_count == 1
    assert spec.objectives[0].planning_outcome == "planned"


def test_ambiguity_resolver_selection_is_applied_to_query_intent() -> None:
    selected_field_id = next(
        field.field_id
        for table in _snapshot().tables
        if table.table_id == WORK_ITEMS_ID
        for field in table.fields
        if field.key == "status"
    )

    def resolve(request: PlannerAmbiguityRequest) -> PlannerAmbiguityDecision:
        assert str(selected_field_id) in request.candidate_ids
        return PlannerAmbiguityDecision(
            mention_id=request.mention_id,
            selected_candidate_ids=(str(selected_field_id),),
        )

    spec = plan_task_v2(
        _request("显示 status"),
        ambiguity_resolver=resolve,
    ).task_spec

    assert spec.query_intents[0].root_table_id == WORK_ITEMS_ID
    assert spec.cost.bound_field_count == 1


def test_ambiguity_resolver_cannot_select_outside_authorized_candidates() -> None:
    def escape_candidates(request: PlannerAmbiguityRequest) -> PlannerAmbiguityDecision:
        return PlannerAmbiguityDecision(
            mention_id=request.mention_id,
            selected_candidate_ids=("not-an-authorized-candidate",),
        )

    with pytest.raises(ValueError, match="task_planner_provider_decision_invalid"):
        plan_task_v2(
            _request("显示 status"),
            ambiguity_resolver=escape_candidates,
        )


def test_ambiguous_binding_without_resolver_requires_clarification() -> None:
    spec = plan_task_v2(_request("显示 status")).task_spec

    assert spec.provider_call_count == 0
    assert spec.objectives[0].planning_outcome == "clarification_required"
    assert spec.objectives[0].denial_reason == "schema_binding_ambiguous"


def test_more_than_four_ambiguities_is_denied_before_resolver_calls() -> None:
    calls: list[PlannerAmbiguityRequest] = []

    def resolve(request: PlannerAmbiguityRequest) -> PlannerAmbiguityDecision:
        calls.append(request)
        return PlannerAmbiguityDecision(
            mention_id=request.mention_id,
            selected_candidate_ids=(request.candidate_ids[0],),
        )

    with pytest.raises(ValueError, match="task_planner_provider_call_limit"):
        plan_task_v2(
            _request("status status status status status"),
            ambiguity_resolver=resolve,
        )

    assert calls == []


@pytest.mark.parametrize(
    ("query", "action_kind"),
    (
        ("为 PRJ-UNKNOWN 创建任务", "task.create"),
        ("为 PRJ-UNKNOWN 新增事项", "record.create"),
    ),
)
def test_create_with_unknown_source_code_requires_authorized_resolution(
    query: str,
    action_kind: str,
) -> None:
    spec = plan_task_v2(_request(query, entities=())).task_spec
    slot = next(item for item in spec.action_slots if item.action_kind == action_kind)

    assert slot.planning_outcome == "clarification_required"
    assert slot.denial_reason == "create_source_unresolved"
    assert slot.target.resolution_status == "unresolved_authorized_lookup_required"


@pytest.mark.parametrize(
    ("query", "table_id"),
    (
        ("创建回滚评审任务", TASKS_ID),
        ("新增回滚评审事项", WORK_ITEMS_ID),
    ),
)
def test_create_denies_assignment_to_visible_read_only_field(
    query: str,
    table_id: UUID,
) -> None:
    snapshot = _snapshot()
    tables = tuple(
        table.model_copy(
            update={
                "fields": tuple(
                    (
                        field.model_copy(update={"writable": False})
                        if table.table_id == table_id and field.key == "title"
                        else field
                    )
                    for field in table.fields
                )
            }
        )
        for table in snapshot.tables
    )
    readonly_snapshot = _snapshot_with_tables(snapshot, tables)

    slot = plan_task_v2(
        _request(query, snapshot=readonly_snapshot)
    ).task_spec.action_slots[0]

    assert slot.planning_outcome == "denied"
    assert slot.denial_reason == "field_permission_denied"


def test_two_updates_extract_values_from_their_own_action_spans() -> None:
    spec = _plan("把 MT-001 的 title 改为 Alpha，然后把 MT-017 的 title 改为 Beta")
    updates = [
        item for item in spec.action_slots if item.action_kind == "record.update"
    ]

    assert [item.target.record_codes for item in updates] == [("MT-001",), ("MT-017",)]
    assert [item.assignments[0].value for item in updates] == ["Alpha", "Beta"]


def test_planner_emits_three_independently_filtered_daily_metrics() -> None:
    intent = plan_task_v2(
        _request("生成今日运营日报：完成、进行中、阻塞和明日优先事项。")
    ).task_spec.query_intents[0]

    assert intent.execution_spec is not None
    aggregates = {item.output_key: item for item in intent.execution_spec.aggregations}
    assert tuple(aggregates) == (
        "completed",
        "in_progress",
        "blocked",
    )
    assert {
        key: item.filter_expression.predicate.value
        for key, item in aggregates.items()
        if item.filter_expression is not None and item.filter_expression.kind == "leaf"
    } == {
        "completed": "done",
        "in_progress": "in_progress",
        "blocked": "blocked",
    }


def test_planner_emits_grouped_unfinished_count_with_having_threshold() -> None:
    intent = plan_task_v2(
        _request("哪些项目同时有两个以上未完成事项？说明潜在交付风险。")
    ).task_spec.query_intents[0]

    assert intent.execution_spec is not None
    aggregate = next(
        item
        for item in intent.execution_spec.aggregations
        if item.output_key == "unfinished_work_items"
    )
    assert aggregate.group_by_field_ids == (
        UUID("10000000-0000-4000-8000-000000000206"),
    )
    assert aggregate.filter_expression is not None
    assert aggregate.filter_expression.kind == "leaf"
    assert aggregate.filter_expression.predicate.operator == "ne"
    assert aggregate.filter_expression.predicate.value == "done"
    assert aggregate.having is not None
    assert aggregate.having.operator == "gte"
    assert aggregate.having.value == 2


def test_planner_emits_enum_field_order_sort_for_blocked_daily_list() -> None:
    intent = plan_task_v2(
        _request("生成阻塞事项清单，按优先级从高到低排序，并统计阻塞数量。")
    ).task_spec.query_intents[0]

    assert intent.execution_spec is not None
    sort = intent.execution_spec.sorts[0]
    assert sort.field_id == UUID("10000000-0000-4000-8000-000000000203")
    assert sort.aggregate_id is None
    assert sort.mode == "field_order"
    assert sort.direction == "asc"
    assert sort.nulls == "last"
    aggregate = next(
        item
        for item in intent.execution_spec.aggregations
        if item.output_key == "blocked_work_items"
    )
    assert aggregate.function == "count"
