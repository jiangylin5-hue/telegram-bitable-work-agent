from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.models.stage06_platform import RecordLink
from app.schemas.authorized_query_plan import (
    AuthorizedRelationSpec,
    QueryTraversalSpec,
)
from app.schemas.stage06_platform import GridViewPresentationCommand
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.authorized_query_records import (
    AuthorizedQueryDenied,
    build_authorized_query_context,
    scan_authorized_records,
)
from app.services.authorized_query_relations import traverse_authorized_links
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
    context: object
    view_context: object
    snapshot: object
    catalog: tuple[AuthorizedRelationSpec, ...]
    projects: object
    work_items: object
    risks: object
    hidden_table: object
    project_name: object
    work_title: object
    work_project: object
    hidden_project: object
    risk_code: object
    risk_work: object
    atlas: object
    hidden: object
    work: object
    risk: object


def _fixture() -> _Fixture:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="Relations",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="Delivery", actor=actor)
    projects = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    work_items = create_table(uow, base.id, name="Work", key="work_items", actor=actor)
    risks = create_table(uow, base.id, name="Risks", key="risks", actor=actor)
    hidden_table = create_table(uow, base.id, name="Hidden", key="hidden", actor=actor)
    project_name = create_field(
        uow, projects.id, name="Name", key="name", field_type="text", actor=actor
    )
    work_title = create_field(
        uow, work_items.id, name="Title", key="title", field_type="text", actor=actor
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
    hidden_project = create_field(
        uow,
        work_items.id,
        name="Private Project",
        key="private_project_link",
        field_type="linked_record",
        options={"target_table_id": str(projects.id)},
        permission_policy={"owner": "hidden"},
        actor=actor,
    )
    risk_code = create_field(
        uow, risks.id, name="Code", key="code", field_type="text", actor=actor
    )
    risk_work = create_field(
        uow,
        risks.id,
        name="Work",
        key="work_link",
        field_type="linked_record",
        options={"target_table_id": str(work_items.id)},
        actor=actor,
    )
    create_field(
        uow, hidden_table.id, name="Name", key="name", field_type="text", actor=actor
    )
    atlas = create_record(uow, projects.id, values={"name": "Atlas"}, actor=actor)
    hidden = create_record(uow, projects.id, values={"name": "Hidden"}, actor=actor)
    work = create_record(
        uow,
        work_items.id,
        values={
            "title": "Launch",
            "project_link": [str(atlas.id), str(hidden.id)],
        },
        actor=actor,
    )
    risk = create_record(
        uow,
        risks.id,
        values={"code": "RISK-001", "work_link": [str(work.id)]},
        actor=actor,
    )

    project_view = create_form_view(
        uow,
        base.id,
        projects.id,
        name="Atlas only",
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
            visible_field_keys=["name"],
            filters=[{"field_key": "name", "operator": "equals", "value": "Atlas"}],
            sort_rules=[],
            group_by_field_key=None,
        ),
    )
    work_view = create_form_view(
        uow,
        base.id,
        work_items.id,
        name="Work",
        view_type="grid",
        config={"fields": ["title", "project_link"]},
        actor=actor,
    )
    work_view.scope = "system_default"
    work_view.version = 1
    work_view.config = canonicalize_v1_presentation(
        uow,
        work_items.id,
        actor=actor,
        command=GridViewPresentationCommand(
            view_type="grid",
            visible_field_keys=["title", "project_link"],
            filters=[{"field_key": "title", "operator": "equals", "value": "Launch"}],
            sort_rules=[],
            group_by_field_key=None,
        ),
    )
    risk_view = create_form_view(
        uow,
        base.id,
        risks.id,
        name="Risks",
        view_type="grid",
        config={"fields": ["code", "work_link"]},
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Relations employee",
        description="Relations fixture",
        telegram_alias=None,
        accessible_tables=[str(projects.id), str(work_items.id), str(risks.id)],
        accessible_views=[str(project_view.id), str(work_view.id), str(risk_view.id)],
        allowed_actions=["query", "summarize"],
        actor=actor,
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
    )
    context = build_authorized_query_context(
        uow,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    view_context = build_authorized_query_context(
        uow,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=(project_view.id, work_view.id, risk_view.id),
        allow_whole_table=False,
    )
    return _Fixture(
        uow=uow,
        actor=actor,
        context=context,
        view_context=view_context,
        snapshot=snapshot,
        catalog=build_authorized_relation_catalog(uow, snapshot),
        projects=projects,
        work_items=work_items,
        risks=risks,
        hidden_table=hidden_table,
        project_name=project_name,
        work_title=work_title,
        work_project=work_project,
        hidden_project=hidden_project,
        risk_code=risk_code,
        risk_work=risk_work,
        atlas=atlas,
        hidden=hidden,
        work=work,
        risk=risk,
    )


def _relation(fixture: _Fixture, field) -> AuthorizedRelationSpec:
    return next(item for item in fixture.catalog if item.link_field_id == field.id)


def _traversal(
    relation: AuthorizedRelationSpec,
    *,
    direction: str,
    traversal_id: str = "traversal-01",
    max_expansion: int = 1000,
) -> QueryTraversalSpec:
    return QueryTraversalSpec(
        traversal_id=traversal_id,
        relation_id=relation.relation_id,
        link_source_table_id=relation.link_source_table_id,
        link_field_id=relation.link_field_id,
        link_target_table_id=relation.link_target_table_id,
        direction=direction,
        max_expansion=max_expansion,
    )


def test_forward_traversal_deduplicates_safe_link_cells_and_emits_proof() -> None:
    fixture = _fixture()
    fixture.work.record_values["project_link"] = [
        str(fixture.atlas.id),
        str(fixture.atlas.id),
        str(fixture.hidden.id),
    ]
    source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.work_items.id,
        required_field_ids=(fixture.work_project.id,),
    )
    relation = _relation(fixture, fixture.work_project)

    result = traverse_authorized_links(
        context=fixture.context,
        source_records=source,
        traversals=(_traversal(relation, direction="forward"),),
        catalog=fixture.catalog,
    )

    assert {item.record_id for item in result.record_set.records} == {
        fixture.atlas.id,
        fixture.hidden.id,
    }
    assert result.traversed_edge_count == 2
    assert len(result.relation_paths) == 2


def test_forward_traversal_treats_authorized_empty_link_as_zero_edges() -> None:
    fixture = _fixture()
    empty = create_record(
        fixture.uow,
        fixture.work_items.id,
        values={"title": "No project"},
        actor=fixture.actor,
    )
    source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.work_items.id,
        required_field_ids=(fixture.work_project.id,),
    )
    relation = _relation(fixture, fixture.work_project)

    result = traverse_authorized_links(
        context=fixture.context,
        source_records=source,
        traversals=(_traversal(relation, direction="forward"),),
        catalog=fixture.catalog,
    )

    assert empty.id not in {
        item.link_source_record_id for item in result.relation_paths
    }
    assert result.traversed_edge_count == 2


def test_reverse_traversal_reauthorizes_source_record() -> None:
    fixture = _fixture()
    source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.projects.id,
        required_field_ids=(fixture.project_name.id,),
    )
    relation = _relation(fixture, fixture.work_project)

    result = traverse_authorized_links(
        context=fixture.context,
        source_records=source,
        traversals=(_traversal(relation, direction="reverse"),),
        catalog=fixture.catalog,
    )

    assert [item.record_id for item in result.record_set.records] == [fixture.work.id]
    assert result.relation_paths[0].link_source_record_id == fixture.work.id
    assert result.relation_paths[0].link_target_record_id in {
        fixture.atlas.id,
        fixture.hidden.id,
    }


def test_reverse_traversal_filters_source_outside_authorized_view() -> None:
    fixture = _fixture()
    hidden_work = create_record(
        fixture.uow,
        fixture.work_items.id,
        values={
            "title": "Not in view",
            "project_link": [str(fixture.atlas.id)],
        },
        actor=fixture.actor,
    )
    source = scan_authorized_records(
        context=fixture.view_context,
        table_id=fixture.projects.id,
        required_field_ids=(fixture.project_name.id,),
    )
    relation = _relation(fixture, fixture.work_project)

    result = traverse_authorized_links(
        context=fixture.view_context,
        source_records=source,
        traversals=(_traversal(relation, direction="reverse"),),
        catalog=fixture.catalog,
    )

    assert [item.record_id for item in result.record_set.records] == [fixture.work.id]
    assert str(hidden_work.id) not in repr(result)


def test_approved_two_hop_reverse_traversal_is_contiguous() -> None:
    fixture = _fixture()
    source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.projects.id,
        required_field_ids=(fixture.project_name.id,),
    )
    work_relation = _relation(fixture, fixture.work_project)
    risk_relation = _relation(fixture, fixture.risk_work)

    result = traverse_authorized_links(
        context=fixture.context,
        source_records=source,
        traversals=(
            _traversal(work_relation, direction="reverse"),
            _traversal(
                risk_relation,
                direction="reverse",
                traversal_id="traversal-02",
            ),
        ),
        catalog=fixture.catalog,
    )

    assert [item.record_id for item in result.record_set.records] == [fixture.risk.id]
    assert result.traversed_edge_count == 3


def test_target_outside_authorized_view_is_absent_without_identifier_leak() -> None:
    fixture = _fixture()
    source = scan_authorized_records(
        context=fixture.view_context,
        table_id=fixture.work_items.id,
        required_field_ids=(fixture.work_project.id,),
    )
    relation = _relation(fixture, fixture.work_project)

    result = traverse_authorized_links(
        context=fixture.view_context,
        source_records=source,
        traversals=(_traversal(relation, direction="forward"),),
        catalog=fixture.catalog,
    )

    assert [item.record_id for item in result.record_set.records] == [fixture.atlas.id]
    assert str(fixture.hidden.id) not in repr(result)


def test_hidden_link_field_is_not_accepted_as_catalog_edge() -> None:
    fixture = _fixture()
    hidden_relation = AuthorizedRelationSpec(
        relation_id=f"relation:{fixture.hidden_project.id}",
        link_source_table_id=fixture.work_items.id,
        link_field_id=fixture.hidden_project.id,
        link_target_table_id=fixture.projects.id,
    )
    source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.work_items.id,
        required_field_ids=(fixture.work_project.id,),
    )

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_relation_not_authorized$",
    ):
        traverse_authorized_links(
            context=fixture.context,
            source_records=source,
            traversals=(_traversal(hidden_relation, direction="forward"),),
            catalog=fixture.catalog,
        )


def test_inaccessible_target_table_is_denied_without_target_details() -> None:
    fixture = _fixture()
    malicious = AuthorizedRelationSpec(
        relation_id="relation:malicious",
        link_source_table_id=fixture.work_items.id,
        link_field_id=fixture.work_project.id,
        link_target_table_id=fixture.hidden_table.id,
    )
    source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.work_items.id,
        required_field_ids=(fixture.work_project.id,),
    )

    with pytest.raises(AuthorizedQueryDenied) as denied:
        traverse_authorized_links(
            context=fixture.context,
            source_records=source,
            traversals=(_traversal(malicious, direction="forward"),),
            catalog=(malicious,),
        )

    assert denied.value.code == "authorized_query_relation_scope_denied"
    assert str(fixture.hidden_table.id) not in str(denied.value)


def test_malformed_reverse_link_row_is_not_permission_proof() -> None:
    fixture = _fixture()
    fixture.uow.add_record_link(
        RecordLink(
            id=uuid4(),
            source_table_id=fixture.risks.id,
            source_record_id=fixture.risk.id,
            source_field_id=fixture.work_project.id,
            target_table_id=fixture.projects.id,
            target_record_id=fixture.atlas.id,
        )
    )
    source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.projects.id,
        required_field_ids=(fixture.project_name.id,),
    )
    relation = _relation(fixture, fixture.work_project)

    result = traverse_authorized_links(
        context=fixture.context,
        source_records=source,
        traversals=(_traversal(relation, direction="reverse"),),
        catalog=fixture.catalog,
    )

    assert [item.record_id for item in result.record_set.records] == [fixture.work.id]
    assert all(
        item.link_source_record_id != fixture.risk.id for item in result.relation_paths
    )


def test_depth_three_and_record_cycle_are_rejected() -> None:
    fixture = _fixture()
    project_source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.projects.id,
        required_field_ids=(fixture.project_name.id,),
    )
    relation = _relation(fixture, fixture.work_project)
    reverse = _traversal(relation, direction="reverse")
    forward = _traversal(
        relation,
        direction="forward",
        traversal_id="traversal-02",
    )

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_traversal_depth_exceeded$",
    ):
        traverse_authorized_links(
            context=fixture.context,
            source_records=project_source,
            traversals=(reverse, forward, reverse),
            catalog=fixture.catalog,
        )
    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_relation_cycle$",
    ):
        traverse_authorized_links(
            context=fixture.context,
            source_records=project_source,
            traversals=(reverse, forward),
            catalog=fixture.catalog,
        )


def test_relation_expansion_1001_refuses_without_partial_result() -> None:
    fixture = _fixture()
    extra_ids = []
    for index in range(999):
        record = create_record(
            fixture.uow,
            fixture.projects.id,
            values={"name": f"Project {index:04d}"},
            actor=fixture.actor,
        )
        extra_ids.append(str(record.id))
    fixture.work.record_values["project_link"] = [
        str(fixture.atlas.id),
        str(fixture.hidden.id),
        *extra_ids,
    ]
    source = scan_authorized_records(
        context=fixture.context,
        table_id=fixture.work_items.id,
        required_field_ids=(fixture.work_project.id,),
    )
    relation = _relation(fixture, fixture.work_project)

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_relation_budget_exceeded$",
    ):
        traverse_authorized_links(
            context=fixture.context,
            source_records=source,
            traversals=(_traversal(relation, direction="forward"),),
            catalog=fixture.catalog,
        )
