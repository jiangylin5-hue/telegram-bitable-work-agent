from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from app.schemas.authorized_query_plan import (
    AuthorizedQueryPlanV1,
    QueryAggregateSpec,
    QueryPredicateGroup,
    QueryPredicateLeaf,
    QuerySortSpec,
    QueryTraversalPathSpec,
    QueryTraversalSpec,
)
from app.schemas.stage06_platform import GridViewPresentationCommand
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.authorized_query_records import AuthorizedQueryDenied
from app.services.authorized_table_query import execute_authorized_query
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    canonicalize_v1_presentation,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


@dataclass(frozen=True)
class _Fixture:
    uow: InMemoryStage06PlatformUnitOfWork
    actor: Actor
    workspace_id: UUID
    employee_id: UUID
    snapshot: object
    project_view_id: UUID
    blocked_work_view_id: UUID
    projects_id: UUID
    work_items_id: UUID
    risks_id: UUID
    project_code_id: UUID
    project_phase_id: UUID
    work_code_id: UUID
    work_status_id: UUID
    work_project_id: UUID
    risk_code_id: UUID
    risk_level_id: UUID
    risk_status_id: UUID
    risk_due_date_id: UUID
    risk_notes_id: UUID
    risk_work_id: UUID
    atlas_id: UUID
    nova_id: UUID
    atlas_blocked_id: UUID
    atlas_done_id: UUID
    nova_blocked_id: UUID
    nova_open_id: UUID
    atlas_high_risk_id: UUID
    atlas_critical_risk_id: UUID
    nova_closed_risk_id: UUID


def _fixture() -> _Fixture:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="Authorized query",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="Delivery", actor=actor)
    projects = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    work_items = create_table(
        uow, base.id, name="Work items", key="work_items", actor=actor
    )
    risks = create_table(uow, base.id, name="Risks", key="risks", actor=actor)
    tasks = create_table(uow, base.id, name="Tasks", key="tasks", actor=actor)
    owners = create_table(uow, base.id, name="Owners", key="owners", actor=actor)
    daily_metrics = create_table(
        uow, base.id, name="Daily metrics", key="daily_metrics", actor=actor
    )
    interactions = create_table(
        uow, base.id, name="Interactions", key="interactions", actor=actor
    )
    project_code = create_field(
        uow,
        projects.id,
        name="Project code",
        key="project_code",
        field_type="text",
        actor=actor,
    )
    project_phase = create_field(
        uow,
        projects.id,
        name="Phase",
        key="phase",
        field_type="status",
        options={"choices": ["discovery", "delivery", "done"]},
        actor=actor,
    )
    work_code = create_field(
        uow,
        work_items.id,
        name="Work code",
        key="work_code",
        field_type="text",
        actor=actor,
    )
    work_status = create_field(
        uow,
        work_items.id,
        name="Status",
        key="status",
        field_type="status",
        options={"choices": ["open", "blocked", "done"]},
        actor=actor,
    )
    work_project = create_field(
        uow,
        work_items.id,
        name="Project",
        key="project_link",
        field_type="linked_record",
        options={"target_table_id": str(projects.id)},
        actor=actor,
    )
    risk_code = create_field(
        uow, risks.id, name="Risk code", key="risk_code", field_type="text", actor=actor
    )
    risk_level = create_field(
        uow,
        risks.id,
        name="Risk level",
        key="risk_level",
        field_type="status",
        options={"choices": ["low", "high", "critical"]},
        actor=actor,
    )
    risk_status = create_field(
        uow,
        risks.id,
        name="Risk status",
        key="risk_status",
        field_type="status",
        options={"choices": ["open", "closed"]},
        actor=actor,
    )
    risk_due_date = create_field(
        uow, risks.id, name="Due date", key="due_date", field_type="date", actor=actor
    )
    risk_notes = create_field(
        uow, risks.id, name="Notes", key="notes", field_type="text", actor=actor
    )
    risk_work = create_field(
        uow,
        risks.id,
        name="Work item",
        key="work_link",
        field_type="linked_record",
        options={"target_table_id": str(work_items.id)},
        actor=actor,
    )
    task_code = create_field(
        uow, tasks.id, name="Task code", key="task_code", field_type="text", actor=actor
    )
    owner_code = create_field(
        uow,
        owners.id,
        name="Owner code",
        key="owner_code",
        field_type="text",
        actor=actor,
    )
    metric_value = create_field(
        uow,
        daily_metrics.id,
        name="Metric value",
        key="metric_value",
        field_type="number",
        actor=actor,
    )
    interaction_text = create_field(
        uow,
        interactions.id,
        name="Interaction",
        key="interaction_text",
        field_type="text",
        actor=actor,
    )

    atlas = create_record(
        uow,
        projects.id,
        values={"project_code": "PRJ-001", "phase": "delivery"},
        actor=actor,
    )
    nova = create_record(
        uow,
        projects.id,
        values={"project_code": "PRJ-002", "phase": "discovery"},
        actor=actor,
    )
    atlas_blocked = create_record(
        uow,
        work_items.id,
        values={
            "work_code": "WORK-001",
            "status": "blocked",
            "project_link": [str(atlas.id)],
        },
        actor=actor,
    )
    atlas_done = create_record(
        uow,
        work_items.id,
        values={
            "work_code": "WORK-002",
            "status": "done",
            "project_link": [str(atlas.id)],
        },
        actor=actor,
    )
    nova_blocked = create_record(
        uow,
        work_items.id,
        values={
            "work_code": "WORK-003",
            "status": "blocked",
            "project_link": [str(nova.id)],
        },
        actor=actor,
    )
    nova_open = create_record(
        uow,
        work_items.id,
        values={
            "work_code": "WORK-004",
            "status": "open",
            "project_link": [str(nova.id)],
        },
        actor=actor,
    )
    atlas_high_risk = create_record(
        uow,
        risks.id,
        values={
            "risk_code": "RISK-001",
            "risk_level": "high",
            "risk_status": "open",
            "due_date": "2026-07-30",
            "work_link": [str(atlas_blocked.id)],
        },
        actor=actor,
    )
    atlas_critical_risk = create_record(
        uow,
        risks.id,
        values={
            "risk_code": "RISK-002",
            "risk_level": "critical",
            "risk_status": "open",
            "due_date": "2026-08-01",
            "work_link": [str(atlas_blocked.id)],
        },
        actor=actor,
    )
    nova_closed_risk = create_record(
        uow,
        risks.id,
        values={
            "risk_code": "RISK-003",
            "risk_level": "low",
            "risk_status": "closed",
            "due_date": "2026-06-01",
            "work_link": [str(nova_blocked.id)],
        },
        actor=actor,
    )
    create_record(uow, tasks.id, values={task_code.key: "TASK-001"}, actor=actor)
    create_record(uow, owners.id, values={owner_code.key: "OWNER-001"}, actor=actor)
    create_record(uow, daily_metrics.id, values={metric_value.key: 7}, actor=actor)
    create_record(
        uow,
        interactions.id,
        values={interaction_text.key: "Daily review"},
        actor=actor,
    )

    project_view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="All projects",
        view_type="grid",
        config={"fields": []},
        actor=actor,
    )
    project_view.scope = "system_default"
    project_view.version = 1
    project_view.config = canonicalize_v1_presentation(
        uow,
        projects.id,
        actor=actor,
        command=GridViewPresentationCommand(
            view_type="grid",
            visible_field_keys=["project_code", "phase"],
            filters=[],
            sort_rules=[],
            group_by_field_key=None,
        ),
    )
    blocked_work_view = create_form_view(
        uow,
        base.id,
        work_items.id,
        name="Blocked work only",
        view_type="grid",
        config={"fields": []},
        actor=actor,
    )
    blocked_work_view.scope = "system_default"
    blocked_work_view.version = 1
    blocked_work_view.config = canonicalize_v1_presentation(
        uow,
        work_items.id,
        actor=actor,
        command=GridViewPresentationCommand(
            view_type="grid",
            visible_field_keys=["work_code", "status", "project_link"],
            filters=[{"field_key": "status", "operator": "is", "value": "blocked"}],
            sort_rules=[],
            group_by_field_key=None,
        ),
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Query employee",
        description="Authorized table-query fixture",
        telegram_alias=None,
        accessible_tables=[
            str(projects.id),
            str(work_items.id),
            str(risks.id),
            str(tasks.id),
            str(owners.id),
            str(daily_metrics.id),
            str(interactions.id),
        ],
        accessible_views=[str(project_view.id), str(blocked_work_view.id)],
        allowed_actions=["query", "summarize"],
        actor=actor,
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
    )
    return _Fixture(
        uow=uow,
        actor=actor,
        workspace_id=workspace.id,
        employee_id=employee.id,
        snapshot=snapshot,
        project_view_id=project_view.id,
        blocked_work_view_id=blocked_work_view.id,
        projects_id=projects.id,
        work_items_id=work_items.id,
        risks_id=risks.id,
        project_code_id=project_code.id,
        project_phase_id=project_phase.id,
        work_code_id=work_code.id,
        work_status_id=work_status.id,
        work_project_id=work_project.id,
        risk_code_id=risk_code.id,
        risk_level_id=risk_level.id,
        risk_status_id=risk_status.id,
        risk_due_date_id=risk_due_date.id,
        risk_notes_id=risk_notes.id,
        risk_work_id=risk_work.id,
        atlas_id=atlas.id,
        nova_id=nova.id,
        atlas_blocked_id=atlas_blocked.id,
        atlas_done_id=atlas_done.id,
        nova_blocked_id=nova_blocked.id,
        nova_open_id=nova_open.id,
        atlas_high_risk_id=atlas_high_risk.id,
        atlas_critical_risk_id=atlas_critical_risk.id,
        nova_closed_risk_id=nova_closed_risk.id,
    )


def _reverse_work_traversal(fixture: _Fixture) -> QueryTraversalSpec:
    relation = next(
        item
        for item in build_authorized_relation_catalog(fixture.uow, fixture.snapshot)
        if item.link_field_id == fixture.work_project_id
    )
    return QueryTraversalSpec(
        traversal_id="traversal-work",
        relation_id=relation.relation_id,
        link_source_table_id=relation.link_source_table_id,
        link_field_id=relation.link_field_id,
        link_target_table_id=relation.link_target_table_id,
        direction="reverse",
        max_expansion=1000,
    )


def _reverse_risk_traversal(fixture: _Fixture) -> QueryTraversalSpec:
    relation = next(
        item
        for item in build_authorized_relation_catalog(fixture.uow, fixture.snapshot)
        if item.link_field_id == fixture.risk_work_id
    )
    return QueryTraversalSpec(
        traversal_id="traversal-risk",
        relation_id=relation.relation_id,
        link_source_table_id=relation.link_source_table_id,
        link_field_id=relation.link_field_id,
        link_target_table_id=relation.link_target_table_id,
        direction="reverse",
        max_expansion=1000,
    )


def _plan(
    fixture: _Fixture,
    *,
    authorized_view_ids: tuple[UUID, ...] = (),
    entity_codes: tuple[str, ...] = (),
    predicate=None,
    traversals: tuple[QueryTraversalSpec, ...] = (),
    traversal_paths: tuple[QueryTraversalPathSpec, ...] = (),
    projection_field_ids: tuple[UUID, ...] = (),
    group_by_field_ids: tuple[UUID, ...] = (),
    aggregates: tuple[QueryAggregateSpec, ...] = (),
    sort_rules: tuple[QuerySortSpec, ...] = (),
    limit: int | None = None,
    max_scan_rows: int = 5000,
    max_relation_expansions: int = 1000,
) -> AuthorizedQueryPlanV1:
    return AuthorizedQueryPlanV1(
        version="authorized-query-plan.v1",
        query_intent_id="intent-01",
        root_table_id=fixture.projects_id,
        authorized_view_ids=authorized_view_ids,
        entity_codes=entity_codes,
        predicate=predicate,
        traversals=traversals,
        projection_field_ids=projection_field_ids,
        group_by_field_ids=group_by_field_ids,
        aggregates=aggregates,
        sort_rules=sort_rules,
        limit=limit,
        max_scan_rows=max_scan_rows,
        max_relation_expansions=max_relation_expansions,
        scope_hash=fixture.snapshot.scope_hash,
        schema_hash=fixture.snapshot.schema_hash,
        traversal_paths=traversal_paths,
    )


def _execute(
    fixture: _Fixture,
    plan: AuthorizedQueryPlanV1,
    *,
    chat_view_ids: tuple[UUID, ...] | None = None,
    allow_whole_table: bool = True,
):
    return execute_authorized_query(
        fixture.uow,
        actor=fixture.actor,
        workspace_id=fixture.workspace_id,
        employee_id=fixture.employee_id,
        chat_view_ids=chat_view_ids,
        snapshot=fixture.snapshot,
        plan=plan,
        allow_whole_table=allow_whole_table,
    )


def _record_value_map(result) -> dict[UUID, dict[UUID, object]]:
    return {
        record.record_id: {item.field_id: item.value for item in record.values}
        for record in result.records
    }


def test_joined_rows_preserve_cross_table_or_projection_and_hash() -> None:
    fixture = _fixture()
    predicate = QueryPredicateGroup(
        predicate_id="predicate-or",
        operator="or",
        children=(
            QueryPredicateLeaf(
                predicate_id="predicate-phase",
                table_id=fixture.projects_id,
                field_id=fixture.project_phase_id,
                operator="eq",
                value="delivery",
            ),
            QueryPredicateLeaf(
                predicate_id="predicate-blocked",
                table_id=fixture.work_items_id,
                field_id=fixture.work_status_id,
                operator="eq",
                value="blocked",
            ),
        ),
    )
    plan = _plan(
        fixture,
        predicate=predicate,
        traversals=(_reverse_work_traversal(fixture),),
        projection_field_ids=(fixture.project_code_id, fixture.work_code_id),
    )

    first = _execute(fixture, plan)
    second = _execute(fixture, plan)

    assert first.result.result_hash == second.result.result_hash
    values = _record_value_map(first.result)
    assert {item.get(fixture.project_code_id) for item in values.values()} == {
        None,
        "PRJ-001",
        "PRJ-002",
    }
    assert {item.get(fixture.work_code_id) for item in values.values()} == {
        None,
        "WORK-001",
        "WORK-002",
        "WORK-003",
    }
    assert fixture.nova_open_id not in values
    assert len(first.result.relation_paths) == 3
    assert {
        (item.link_target_record_id, item.link_source_record_id)
        for item in first.result.relation_paths
    } == {
        (fixture.atlas_id, fixture.atlas_blocked_id),
        (fixture.atlas_id, fixture.atlas_done_id),
        (fixture.nova_id, fixture.nova_blocked_id),
    }
    assert {
        (item.table_id, item.record_id) for item in first.result.source_versions
    } == {
        (fixture.projects_id, fixture.atlas_id),
        (fixture.projects_id, fixture.nova_id),
        (fixture.work_items_id, fixture.atlas_blocked_id),
        (fixture.work_items_id, fixture.atlas_done_id),
        (fixture.work_items_id, fixture.nova_blocked_id),
    }


def test_view_scope_excludes_rejected_target_from_artifact_and_hash_input() -> None:
    fixture = _fixture()
    plan = _plan(
        fixture,
        authorized_view_ids=(fixture.project_view_id, fixture.blocked_work_view_id),
        traversals=(_reverse_work_traversal(fixture),),
        projection_field_ids=(fixture.project_code_id, fixture.work_code_id),
    )

    artifact = _execute(
        fixture,
        plan,
        chat_view_ids=(fixture.project_view_id, fixture.blocked_work_view_id),
        allow_whole_table=False,
    )

    serialized = artifact.model_dump_json()
    assert str(fixture.atlas_done_id) not in serialized
    assert str(fixture.nova_open_id) not in serialized
    assert {item.link_source_record_id for item in artifact.result.relation_paths} == {
        fixture.atlas_blocked_id,
        fixture.nova_blocked_id,
    }
    assert artifact.result.scanned_record_count == 4


def test_entity_code_resolution_is_exact_and_single_table() -> None:
    fixture = _fixture()
    plan = _plan(
        fixture,
        entity_codes=("PRJ-002",),
        projection_field_ids=(fixture.project_code_id,),
    )

    artifact = _execute(fixture, plan)

    assert [item.record_id for item in artifact.result.records] == [fixture.nova_id]
    assert artifact.result.records[0].values[0].value == "PRJ-002"


def test_join_aggregate_computes_complete_groups_before_limit() -> None:
    fixture = _fixture()
    unfinished = QueryPredicateLeaf(
        predicate_id="predicate-unfinished",
        table_id=fixture.work_items_id,
        field_id=fixture.work_status_id,
        operator="ne",
        value="done",
    )
    aggregate = QueryAggregateSpec(
        aggregate_id="aggregate-work-count",
        output_key="work_count",
        function="count",
        table_id=fixture.work_items_id,
        field_id=None,
        filter_predicate=None,
        group_by_field_ids=(fixture.work_status_id,),
        having=None,
    )
    sort = QuerySortSpec(
        sort_id="sort-work-count",
        table_id=None,
        field_id=None,
        aggregate_id=aggregate.aggregate_id,
        mode="natural",
        direction="desc",
        nulls="last",
    )
    plan = _plan(
        fixture,
        predicate=unfinished,
        traversals=(_reverse_work_traversal(fixture),),
        projection_field_ids=(fixture.work_code_id,),
        group_by_field_ids=(fixture.work_status_id,),
        aggregates=(aggregate,),
        sort_rules=(sort,),
        limit=2,
    )

    artifact = _execute(fixture, plan)

    assert [item.group_key for item in artifact.result.groups] == [
        ("blocked",),
        ("open",),
    ]
    assert [item.value for item in artifact.result.aggregates] == [2, 1]
    assert artifact.result.truncated is False
    assert artifact.result.scanned_record_count == 6


def test_two_hop_max_risk_applies_negative_empty_and_date_predicates() -> None:
    fixture = _fixture()
    predicate = QueryPredicateGroup(
        predicate_id="predicate-risk-and",
        operator="and",
        children=(
            QueryPredicateLeaf(
                predicate_id="predicate-risk-open",
                table_id=fixture.risks_id,
                field_id=fixture.risk_status_id,
                operator="ne",
                value="closed",
            ),
            QueryPredicateLeaf(
                predicate_id="predicate-risk-date",
                table_id=fixture.risks_id,
                field_id=fixture.risk_due_date_id,
                operator="after",
                value="2026-07-01",
            ),
            QueryPredicateLeaf(
                predicate_id="predicate-risk-notes-empty",
                table_id=fixture.risks_id,
                field_id=fixture.risk_notes_id,
                operator="is_empty",
                value=None,
            ),
        ),
    )
    sort = QuerySortSpec(
        sort_id="sort-risk-level",
        table_id=fixture.risks_id,
        field_id=fixture.risk_level_id,
        aggregate_id=None,
        mode="field_order",
        direction="desc",
        nulls="last",
    )
    plan = _plan(
        fixture,
        predicate=predicate,
        traversals=(
            _reverse_work_traversal(fixture),
            _reverse_risk_traversal(fixture),
        ),
        projection_field_ids=(fixture.project_code_id, fixture.risk_code_id),
        sort_rules=(sort,),
        limit=1,
    )

    artifact = _execute(fixture, plan)

    values = _record_value_map(artifact.result)
    assert set(values) == {fixture.atlas_id, fixture.atlas_critical_risk_id}
    assert values[fixture.atlas_critical_risk_id][fixture.risk_code_id] == "RISK-002"
    assert len(artifact.result.relation_paths) == 2
    assert {
        (item.table_id, item.record_id) for item in artifact.result.source_versions
    } == {
        (fixture.projects_id, fixture.atlas_id),
        (fixture.work_items_id, fixture.atlas_blocked_id),
        (fixture.risks_id, fixture.atlas_critical_risk_id),
    }
    assert artifact.result.scanned_record_count == 9
    assert artifact.result.traversed_edge_count == 7
    assert artifact.result.truncated is True


def test_left_traversal_path_preserves_primary_rows_without_matching_risk() -> None:
    fixture = _fixture()
    work_step = _reverse_work_traversal(fixture)
    risk_step = _reverse_risk_traversal(fixture)
    open_risk = QueryPredicateLeaf(
        predicate_id="predicate-open-risk",
        table_id=fixture.risks_id,
        field_id=fixture.risk_status_id,
        operator="eq",
        value="open",
    )
    plan = _plan(
        fixture,
        entity_codes=("PRJ-002",),
        traversal_paths=(
            QueryTraversalPathSpec(
                path_id="path-work",
                target_table_id=fixture.work_items_id,
                purpose="project",
                join_mode="inner",
                steps=(
                    work_step.model_copy(update={"traversal_id": "path-work-step-01"}),
                ),
                predicate=None,
            ),
            QueryTraversalPathSpec(
                path_id="path-risk",
                target_table_id=fixture.risks_id,
                purpose="project",
                join_mode="left",
                steps=(
                    work_step.model_copy(update={"traversal_id": "path-risk-step-01"}),
                    risk_step.model_copy(update={"traversal_id": "path-risk-step-02"}),
                ),
                predicate=open_risk,
            ),
        ),
        projection_field_ids=(
            fixture.project_code_id,
            fixture.work_code_id,
            fixture.risk_code_id,
        ),
    )

    artifact = _execute(fixture, plan)
    values = _record_value_map(artifact.result)

    assert set(values) == {
        fixture.nova_id,
        fixture.nova_blocked_id,
        fixture.nova_open_id,
    }
    assert not {
        fixture.atlas_high_risk_id,
        fixture.atlas_critical_risk_id,
        fixture.nova_closed_risk_id,
    } & set(values)


def test_optional_context_path_is_not_materialized_when_target_is_not_consumed() -> (
    None
):
    fixture = _fixture()
    work_step = _reverse_work_traversal(fixture)
    plan = _plan(
        fixture,
        entity_codes=("PRJ-001",),
        traversal_paths=(
            QueryTraversalPathSpec(
                path_id="path-work-context",
                target_table_id=fixture.work_items_id,
                purpose="project",
                join_mode="left",
                steps=(
                    work_step.model_copy(
                        update={"traversal_id": "path-work-context-step-01"}
                    ),
                ),
                predicate=None,
            ),
        ),
        projection_field_ids=(fixture.project_code_id,),
    )

    artifact = _execute(fixture, plan)

    assert [item.record_id for item in artifact.result.records] == [fixture.atlas_id]
    assert artifact.result.relation_paths == ()
    assert {
        (item.table_id, item.record_id) for item in artifact.result.source_versions
    } == {(fixture.projects_id, fixture.atlas_id)}
    assert artifact.result.traversed_edge_count == 0


def test_semi_traversal_path_keeps_only_roots_with_matching_related_records() -> None:
    fixture = _fixture()
    high_risk = QueryPredicateLeaf(
        predicate_id="predicate-high-risk",
        table_id=fixture.risks_id,
        field_id=fixture.risk_level_id,
        operator="eq",
        value="high",
    )
    plan = _plan(
        fixture,
        traversal_paths=(
            QueryTraversalPathSpec(
                path_id="path-risk-exists",
                target_table_id=fixture.risks_id,
                purpose="exists",
                join_mode="semi",
                steps=(
                    _reverse_work_traversal(fixture).model_copy(
                        update={"traversal_id": "path-risk-exists-step-01"}
                    ),
                    _reverse_risk_traversal(fixture).model_copy(
                        update={"traversal_id": "path-risk-exists-step-02"}
                    ),
                ),
                predicate=high_risk,
            ),
        ),
        projection_field_ids=(fixture.project_code_id,),
    )

    artifact = _execute(fixture, plan)

    assert [item.record_id for item in artifact.result.records] == [fixture.atlas_id]


def test_scan_and_relation_budgets_refuse_without_partial_artifact() -> None:
    fixture = _fixture()
    scan_plan = _plan(
        fixture,
        projection_field_ids=(fixture.project_code_id,),
        max_scan_rows=1,
    )

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_scan_budget_exceeded$",
    ):
        _execute(fixture, scan_plan)

    relation_plan = _plan(
        fixture,
        traversals=(_reverse_work_traversal(fixture),),
        projection_field_ids=(fixture.work_code_id,),
        max_relation_expansions=1,
    )
    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_relation_budget_exceeded$",
    ):
        _execute(fixture, relation_plan)


def test_scope_and_schema_are_revalidated_before_execution() -> None:
    fixture = _fixture()
    plan = _plan(fixture, projection_field_ids=(fixture.project_code_id,))
    employee = fixture.uow.get_digital_employee(fixture.employee_id)
    employee.version += 1

    with pytest.raises(AuthorizedQueryDenied, match="^authorized_query_scope_drift$"):
        _execute(fixture, plan)

    fixture = _fixture()
    plan = _plan(fixture, projection_field_ids=(fixture.project_code_id,))
    project_table = fixture.uow.get_table(fixture.projects_id)
    create_field(
        fixture.uow,
        project_table.id,
        name="New visible field",
        key="new_visible_field",
        field_type="text",
        actor=fixture.actor,
    )

    with pytest.raises(AuthorizedQueryDenied, match="^authorized_query_schema_drift$"):
        _execute(fixture, plan)


def test_whole_table_access_requires_explicit_authority() -> None:
    fixture = _fixture()
    plan = _plan(fixture, projection_field_ids=(fixture.project_code_id,))

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_view_scope_denied$",
    ):
        _execute(fixture, plan, chat_view_ids=(), allow_whole_table=False)
