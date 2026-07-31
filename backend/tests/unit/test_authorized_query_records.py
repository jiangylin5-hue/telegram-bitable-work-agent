from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from app.schemas.authorized_query_plan import (
    QueryPredicateGroup,
    QueryPredicateLeaf,
)
from app.schemas.stage06_platform import GridViewPresentationCommand
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.authorized_query_records import (
    AuthorizedQueryDenied,
    build_authorized_query_context,
    build_authorized_relation_catalog,
    filter_records,
    project_records,
    resolve_authorized_entities,
    scan_authorized_records,
)
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
    base_id: UUID
    employee_id: UUID
    projects_id: UUID
    work_items_id: UUID
    hidden_target_id: UUID
    blocked_view_id: UUID
    other_view_id: UUID
    fields: dict[str, object]
    records: dict[str, object]
    snapshot: object


def _fixture() -> _Fixture:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="Authorized Query",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="Delivery", actor=actor)
    projects = create_table(
        uow,
        base.id,
        name="Projects",
        key="projects",
        actor=actor,
    )
    work_items = create_table(
        uow,
        base.id,
        name="Work Items",
        key="work_items",
        actor=actor,
    )
    hidden_target = create_table(
        uow,
        base.id,
        name="Hidden Target",
        key="hidden_target",
        actor=actor,
    )
    project_name = create_field(
        uow,
        projects.id,
        name="Name",
        key="name",
        field_type="text",
        actor=actor,
    )
    hidden_name = create_field(
        uow,
        hidden_target.id,
        name="Name",
        key="name",
        field_type="text",
        actor=actor,
    )
    code = create_field(
        uow,
        work_items.id,
        name="Code",
        key="code",
        field_type="text",
        actor=actor,
    )
    title = create_field(
        uow,
        work_items.id,
        name="Title",
        key="title",
        field_type="text",
        actor=actor,
    )
    status = create_field(
        uow,
        work_items.id,
        name="Status",
        key="status",
        field_type="status",
        options={"choices": ["planned", "done", "blocked"]},
        actor=actor,
    )
    score = create_field(
        uow,
        work_items.id,
        name="Score",
        key="score",
        field_type="number",
        actor=actor,
    )
    due_date = create_field(
        uow,
        work_items.id,
        name="Due Date",
        key="due_date",
        field_type="date",
        actor=actor,
    )
    tags = create_field(
        uow,
        work_items.id,
        name="Tags",
        key="tags",
        field_type="multi_select",
        options={"choices": ["delivery", "urgent", "backend"]},
        actor=actor,
    )
    reviewed = create_field(
        uow,
        work_items.id,
        name="Reviewed",
        key="reviewed",
        field_type="checkbox",
        actor=actor,
    )
    aliases = create_field(
        uow,
        work_items.id,
        name="Aliases",
        key="aliases",
        field_type="multi_select",
        options={"choices": ["Legacy", "MT-001"]},
        actor=actor,
    )
    project_link = create_field(
        uow,
        work_items.id,
        name="Project",
        key="project_link",
        field_type="linked_record",
        options={"target_table_id": str(projects.id)},
        actor=actor,
    )
    hidden_link = create_field(
        uow,
        work_items.id,
        name="Hidden Link",
        key="hidden_link",
        field_type="linked_record",
        options={"target_table_id": str(projects.id)},
        permission_policy={"owner": "hidden"},
        actor=actor,
    )
    inaccessible_link = create_field(
        uow,
        work_items.id,
        name="Inaccessible Link",
        key="inaccessible_link",
        field_type="linked_record",
        options={"target_table_id": str(hidden_target.id)},
        actor=actor,
    )
    secret = create_field(
        uow,
        work_items.id,
        name="Secret",
        key="secret",
        field_type="text",
        permission_policy={"owner": "hidden"},
        actor=actor,
    )

    project = create_record(
        uow,
        projects.id,
        values={"name": "Atlas"},
        actor=actor,
    )
    first = create_record(
        uow,
        work_items.id,
        values={
            "code": "MT-001",
            "title": "Shared",
            "status": "blocked",
            "score": 9,
            "due_date": "2026-07-31",
            "tags": ["delivery", "urgent"],
            "reviewed": True,
            "aliases": ["Legacy"],
            "project_link": [str(project.id)],
            "secret": "never-return",
        },
        actor=actor,
    )
    first.version = 7
    second = create_record(
        uow,
        work_items.id,
        values={
            "code": "MT-002",
            "title": "Shared",
            "status": "done",
            "score": 3,
            "due_date": "2026-08-05",
            "tags": ["backend"],
            "reviewed": False,
            "aliases": ["MT-001"],
            "project_link": [str(project.id)],
        },
        actor=actor,
    )
    inactive = create_record(
        uow,
        work_items.id,
        values={
            "code": "MT-003",
            "title": "Inactive",
            "status": "blocked",
        },
        actor=actor,
    )
    inactive.record_status = "deleted"

    blocked_view = create_form_view(
        uow,
        base.id,
        work_items.id,
        name="Blocked",
        view_type="grid",
        config={"fields": []},
        actor=actor,
    )
    blocked_view.scope = "system_default"
    blocked_view.version = 1
    blocked_view.config = canonicalize_v1_presentation(
        uow,
        work_items.id,
        actor=actor,
        command=GridViewPresentationCommand(
            view_type="grid",
            visible_field_keys=[
                "code",
                "title",
                "status",
                "score",
                "due_date",
                "tags",
                "reviewed",
                "aliases",
                "project_link",
            ],
            filters=[{"field_key": "status", "operator": "is", "value": "blocked"}],
            sort_rules=[],
            group_by_field_key=None,
        ),
    )
    other_view = create_form_view(
        uow,
        base.id,
        work_items.id,
        name="All",
        view_type="grid",
        config={"fields": ["code", "title", "status"]},
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Query employee",
        description="Authorized record source fixture",
        telegram_alias=None,
        accessible_tables=[str(projects.id), str(work_items.id)],
        accessible_views=[str(blocked_view.id)],
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
        base_id=base.id,
        employee_id=employee.id,
        projects_id=projects.id,
        work_items_id=work_items.id,
        hidden_target_id=hidden_target.id,
        blocked_view_id=blocked_view.id,
        other_view_id=other_view.id,
        fields={
            item.key: item
            for item in (
                project_name,
                hidden_name,
                code,
                title,
                status,
                score,
                due_date,
                tags,
                reviewed,
                aliases,
                project_link,
                hidden_link,
                inaccessible_link,
                secret,
            )
        },
        records={
            "project": project,
            "first": first,
            "second": second,
            "inactive": inactive,
        },
        snapshot=snapshot,
    )


def _context(
    fixture: _Fixture,
    *,
    chat_views: tuple[UUID, ...] | None = None,
    allow_whole_table: bool = False,
):
    return build_authorized_query_context(
        fixture.uow,
        workspace_id=fixture.workspace_id,
        base_id=fixture.base_id,
        employee_id=fixture.employee_id,
        actor=fixture.actor,
        snapshot=fixture.snapshot,
        chat_authorized_view_ids=chat_views,
        allow_whole_table=allow_whole_table,
    )


def _values(record) -> dict[UUID, object]:
    return {item.field_id: item.value for item in record.values}


def test_relation_catalog_contains_only_visible_in_scope_edges() -> None:
    fixture = _fixture()

    catalog = build_authorized_relation_catalog(fixture.uow, fixture.snapshot)

    assert [item.link_field_id for item in catalog] == [
        fixture.fields["project_link"].id
    ]
    assert catalog[0].link_source_table_id == fixture.work_items_id
    assert catalog[0].link_target_table_id == fixture.projects_id


def test_employee_inaccessible_table_is_denied_before_enumeration() -> None:
    fixture = _fixture()
    context = _context(fixture, allow_whole_table=True)

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_table_scope_denied$",
    ):
        scan_authorized_records(
            context=context,
            table_id=fixture.hidden_target_id,
            required_field_ids=(),
        )


def test_chat_view_scope_cannot_expand_employee_scope() -> None:
    fixture = _fixture()

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_view_scope_denied$",
    ):
        _context(fixture, chat_views=(fixture.other_view_id,))


def test_view_scope_excludes_nonmatching_and_inactive_records_and_keeps_version() -> (
    None
):
    fixture = _fixture()
    context = _context(fixture, chat_views=(fixture.blocked_view_id,))

    records = scan_authorized_records(
        context=context,
        table_id=fixture.work_items_id,
        required_field_ids=(
            fixture.fields["code"].id,
            fixture.fields["title"].id,
        ),
    )

    assert [item.record_id for item in records.records] == [fixture.records["first"].id]
    assert records.records[0].version == 7
    assert records.scanned_record_count == 1


def test_caller_hidden_field_is_never_projected() -> None:
    fixture = _fixture()
    context = _context(fixture, allow_whole_table=True)
    safe = scan_authorized_records(
        context=context,
        table_id=fixture.work_items_id,
        required_field_ids=(fixture.fields["title"].id,),
    )

    assert all(
        fixture.fields["secret"].id not in _values(item) for item in safe.records
    )
    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_field_scope_denied$",
    ):
        scan_authorized_records(
            context=context,
            table_id=fixture.work_items_id,
            required_field_ids=(fixture.fields["secret"].id,),
        )


def test_entity_resolution_prefers_exact_code_and_reports_duplicate_label() -> None:
    fixture = _fixture()
    records = scan_authorized_records(
        context=_context(fixture, allow_whole_table=True),
        table_id=fixture.work_items_id,
        required_field_ids=(
            fixture.fields["code"].id,
            fixture.fields["title"].id,
            fixture.fields["aliases"].id,
        ),
    )

    resolved = resolve_authorized_entities(
        records,
        selectors=("MT-001", "Shared", "Legacy"),
        code_field_id=fixture.fields["code"].id,
        display_field_id=fixture.fields["title"].id,
        alias_field_ids=(fixture.fields["aliases"].id,),
    )

    by_selector = {item.selector: item for item in resolved}
    assert by_selector["MT-001"].status == "resolved"
    assert by_selector["MT-001"].record_ids == (fixture.records["first"].id,)
    assert by_selector["Shared"].status == "ambiguous"
    assert set(by_selector["Shared"].record_ids) == {
        fixture.records["first"].id,
        fixture.records["second"].id,
    }
    assert by_selector["Legacy"].status == "resolved"


def test_typed_filtering_executes_explicit_and_or_only() -> None:
    fixture = _fixture()
    required = tuple(
        fixture.fields[key].id
        for key in (
            "title",
            "status",
            "score",
            "due_date",
            "tags",
            "reviewed",
            "project_link",
        )
    )
    records = scan_authorized_records(
        context=_context(fixture, allow_whole_table=True),
        table_id=fixture.work_items_id,
        required_field_ids=required,
    )
    and_predicate = QueryPredicateGroup(
        predicate_id="and-root",
        operator="and",
        children=(
            QueryPredicateLeaf(
                predicate_id="score",
                table_id=fixture.work_items_id,
                field_id=fixture.fields["score"].id,
                operator="gte",
                value=8,
            ),
            QueryPredicateLeaf(
                predicate_id="tags",
                table_id=fixture.work_items_id,
                field_id=fixture.fields["tags"].id,
                operator="contains_all",
                value=["delivery", "urgent"],
            ),
            QueryPredicateLeaf(
                predicate_id="date",
                table_id=fixture.work_items_id,
                field_id=fixture.fields["due_date"].id,
                operator="before",
                value="2026-08-01",
            ),
            QueryPredicateLeaf(
                predicate_id="reviewed",
                table_id=fixture.work_items_id,
                field_id=fixture.fields["reviewed"].id,
                operator="is_true",
                value=None,
            ),
            QueryPredicateLeaf(
                predicate_id="link",
                table_id=fixture.work_items_id,
                field_id=fixture.fields["project_link"].id,
                operator="contains_record",
                value=str(fixture.records["project"].id),
            ),
        ),
    )
    or_predicate = QueryPredicateGroup(
        predicate_id="or-root",
        operator="or",
        children=(
            QueryPredicateLeaf(
                predicate_id="blocked",
                table_id=fixture.work_items_id,
                field_id=fixture.fields["status"].id,
                operator="eq",
                value="blocked",
            ),
            QueryPredicateLeaf(
                predicate_id="done",
                table_id=fixture.work_items_id,
                field_id=fixture.fields["status"].id,
                operator="eq",
                value="done",
            ),
        ),
    )

    filtered = filter_records(
        records, predicate=and_predicate, snapshot=fixture.snapshot
    )
    either = filter_records(records, predicate=or_predicate, snapshot=fixture.snapshot)

    assert [item.record_id for item in filtered.records] == [
        fixture.records["first"].id
    ]
    assert {item.record_id for item in either.records} == {
        fixture.records["first"].id,
        fixture.records["second"].id,
    }


def test_filter_rejects_operator_outside_authorized_field_type_matrix() -> None:
    fixture = _fixture()
    records = scan_authorized_records(
        context=_context(fixture, allow_whole_table=True),
        table_id=fixture.work_items_id,
        required_field_ids=(fixture.fields["score"].id,),
    )
    invalid = QueryPredicateLeaf(
        predicate_id="invalid-number-contains",
        table_id=fixture.work_items_id,
        field_id=fixture.fields["score"].id,
        operator="contains",
        value="9",
    )

    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_operator_type_invalid$",
    ):
        filter_records(records, predicate=invalid, snapshot=fixture.snapshot)


def test_projection_is_immutable_and_scan_budget_refuses_partial_result() -> None:
    fixture = _fixture()
    records = scan_authorized_records(
        context=_context(fixture, allow_whole_table=True),
        table_id=fixture.work_items_id,
        required_field_ids=(
            fixture.fields["code"].id,
            fixture.fields["title"].id,
        ),
    )
    projected = project_records(records, (fixture.fields["title"].id,))

    assert all(
        tuple(_values(item)) == (fixture.fields["title"].id,)
        for item in projected.records
    )
    with pytest.raises(
        AuthorizedQueryDenied,
        match="^authorized_query_scan_budget_exceeded$",
    ):
        scan_authorized_records(
            context=_context(fixture, allow_whole_table=True),
            table_id=fixture.work_items_id,
            required_field_ids=(fixture.fields["title"].id,),
            max_scan_rows=1,
        )
