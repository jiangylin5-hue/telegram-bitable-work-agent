from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.agent_task_spec_v2 import (
    AuthorizedEntitySpec,
    AuthorizedSchemaSnapshot,
    authorized_schema_sha256,
)
from app.services.agent_query_lexical import extract_lexical_query
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.agent_schema_binding import (
    bind_lexical_query,
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_table,
    create_workspace,
)


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    viewer = Actor(actor_type="user", actor_id="viewer-1", role="viewer")
    workspace = create_workspace(
        uow, name="Planner Binder", owner_user_id=owner.actor_id, actor=owner
    )
    base = create_base(uow, workspace.id, name="Delivery", actor=owner)
    projects = create_table(uow, base.id, name="项目", key="projects", actor=owner)
    work_items = create_table(
        uow, base.id, name="工作项", key="work_items", actor=owner
    )
    create_field(
        uow,
        projects.id,
        name="项目编号",
        key="project_code",
        field_type="text",
        options={"aliases": ["项目编码"]},
        actor=owner,
    )
    create_field(
        uow,
        projects.id,
        name="状态",
        key="status",
        field_type="status",
        options={"choices": ["active", "paused"], "default": "active"},
        actor=owner,
    )
    create_field(
        uow,
        projects.id,
        name="客户密钥",
        key="customer_secret",
        field_type="text",
        permission_policy={"viewer": "hidden"},
        actor=owner,
    )
    create_field(
        uow,
        work_items.id,
        name="事项编号",
        key="ticket_code",
        field_type="text",
        actor=owner,
    )
    create_field(
        uow,
        work_items.id,
        name="状态",
        key="status",
        field_type="status",
        options={"choices": ["planned", "blocked", "done"]},
        actor=owner,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Planner",
        description="Planner fixture",
        telegram_alias=None,
        accessible_tables=[str(projects.id)],
        accessible_views=[],
        allowed_actions=["query", "summarize"],
        actor=owner,
    )
    return uow, owner, viewer, workspace, base, projects, work_items, employee


def _lexical(query: str):
    from datetime import datetime

    return extract_lexical_query(
        query,
        clock=datetime.fromisoformat("2026-07-29T00:00:00+08:00"),
        timezone_name="Asia/Shanghai",
    )


def test_snapshot_intersects_employee_tables_and_caller_field_visibility() -> None:
    uow, _owner, viewer, workspace, _base, projects, work_items, employee = _fixture()

    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=viewer,
    )

    assert [item.table_id for item in snapshot.tables] == [projects.id]
    assert work_items.id not in {item.table_id for item in snapshot.tables}
    fields = {item.key: item for item in snapshot.tables[0].fields}
    assert set(fields) == {"project_code", "status"}
    assert fields["project_code"].aliases == ("项目编码",)
    assert fields["status"].choices == ("active", "paused")
    assert fields["status"].default_value == "active"
    assert all(item.writable is False for item in fields.values())
    assert "客户密钥" not in snapshot.model_dump_json()


def test_stage12_snapshot_requires_v2_policy_and_intersects_read_write_masking() -> None:
    uow, owner, _viewer, workspace, _base, projects, _work_items, employee = _fixture()
    fields = {item.key: item for item in uow.list_fields(projects.id)}

    with pytest.raises(
        PlatformValidationError,
        match="digital_employee_field_policy_v2_required",
    ):
        build_authorized_schema_snapshot(
            uow,
            workspace_id=workspace.id,
            employee_id=employee.id,
            actor=owner,
            require_field_policy_v2=True,
        )

    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=(
            fields["project_code"].id,
            fields["status"].id,
            fields["customer_secret"].id,
        ),
        writable_field_ids=(fields["status"].id,),
        redacted_field_ids=(fields["customer_secret"].id,),
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
        require_field_policy_v2=True,
    )

    visible = {item.key: item for item in snapshot.tables[0].fields}
    assert set(visible) == {"project_code", "status"}
    assert visible["project_code"].writable is False
    assert visible["status"].writable is True
    assert snapshot.field_policy_version == "stage12-field-policy.v2"
    assert snapshot.field_policy_hash is not None


def test_stage12_snapshot_rejects_stale_policy_field_ids() -> None:
    uow, owner, _viewer, workspace, _base, _projects, _work_items, employee = _fixture()
    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=(uuid4(),),
        writable_field_ids=(),
    )

    with pytest.raises(
        PlatformValidationError,
        match="digital_employee_field_policy_v2_stale",
    ):
        build_authorized_schema_snapshot(
            uow,
            workspace_id=workspace.id,
            employee_id=employee.id,
            actor=owner,
            require_field_policy_v2=True,
        )


def test_snapshot_hash_changes_when_authorized_schema_changes() -> None:
    uow, owner, _viewer, workspace, _base, projects, _work_items, employee = _fixture()
    before = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )
    create_field(
        uow,
        projects.id,
        name="阶段",
        key="phase",
        field_type="single_select",
        options={"choices": ["planning", "delivery"]},
        actor=owner,
    )
    after = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )

    assert before.schema_hash != after.schema_hash
    assert before.scope_hash == after.scope_hash


def test_relation_catalog_uses_only_snapshot_visible_link_fields() -> None:
    uow, owner, _viewer, workspace, _base, projects, work_items, employee = _fixture()
    employee.accessible_tables = [str(projects.id), str(work_items.id)]
    visible = create_field(
        uow,
        work_items.id,
        name="Project",
        key="project_link",
        field_type="linked_record",
        options={"target_table_id": str(projects.id)},
        actor=owner,
    )
    create_field(
        uow,
        work_items.id,
        name="Private Project",
        key="private_project_link",
        field_type="linked_record",
        options={"target_table_id": str(projects.id)},
        permission_policy={"owner": "hidden"},
        actor=owner,
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )

    catalog = build_authorized_relation_catalog(uow, snapshot)

    assert [item.link_field_id for item in catalog] == [visible.id]


def test_binder_resolves_exact_key_name_alias_enum_and_authorized_entity() -> None:
    uow, owner, _viewer, workspace, _base, projects, _work_items, employee = _fixture()
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )
    atlas = AuthorizedEntitySpec(
        entity_id=uuid4(),
        table_id=projects.id,
        code="PRJ-ATLAS",
        label="Atlas",
        aliases=("阿特拉斯",),
    )

    result = bind_lexical_query(
        _lexical("查询项目表的 project_code 和项目编码，筛选 paused 的 PRJ-ATLAS"),
        snapshot,
        authorized_entities=(atlas,),
    )

    assert {item.table_key for item in result.bound_tables} == {"projects"}
    assert {item.field_key for item in result.bound_fields} == {"project_code"}
    assert {item.value for item in result.bound_enum_values} == {"paused"}
    assert [item.code for item in result.bound_entities] == ["PRJ-ATLAS"]
    assert result.ambiguous_candidates == ()
    assert result.unresolved_mentions == ()


def test_exact_code_outranks_alias_and_unknown_code_requires_authorized_lookup() -> (
    None
):
    uow, owner, _viewer, workspace, _base, projects, _work_items, employee = _fixture()
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )
    exact = AuthorizedEntitySpec(
        entity_id=uuid4(),
        table_id=projects.id,
        code="PRJ-ATLAS",
        label="Atlas",
        aliases=("PRJ-BEACON",),
    )

    result = bind_lexical_query(
        _lexical("比较 PRJ-ATLAS 和 PRJ-UNKNOWN"),
        snapshot,
        authorized_entities=(exact,),
    )

    assert [item.code for item in result.bound_entities] == ["PRJ-ATLAS"]
    assert [(item.text, item.reason) for item in result.unresolved_mentions] == [
        ("PRJ-UNKNOWN", "unresolved_authorized_lookup_required")
    ]


def test_duplicate_field_name_is_ambiguous_without_table_context() -> None:
    uow, owner, _viewer, workspace, _base, projects, work_items, employee = _fixture()
    employee.accessible_tables = [str(projects.id), str(work_items.id)]
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )

    ambiguous = bind_lexical_query(_lexical("筛选状态"), snapshot)
    scoped = bind_lexical_query(_lexical("筛选工作项状态为 blocked"), snapshot)

    assert len(ambiguous.ambiguous_candidates) == 1
    assert ambiguous.ambiguous_candidates[0].kind == "field"
    assert len(ambiguous.ambiguous_candidates[0].candidate_ids) == 2
    assert [item.field_key for item in scoped.bound_fields] == ["status"]
    assert scoped.bound_fields[0].table_id == work_items.id
    assert [item.value for item in scoped.bound_enum_values] == ["blocked"]


def test_authorized_entity_table_disambiguates_field_and_enum_binding() -> None:
    uow, owner, _viewer, workspace, _base, projects, work_items, employee = _fixture()
    employee.accessible_tables = [str(projects.id), str(work_items.id)]
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )
    work_item = AuthorizedEntitySpec(
        entity_id=uuid4(),
        table_id=work_items.id,
        code="MT-001",
        label="Atlas checklist",
        aliases=(),
    )

    result = bind_lexical_query(
        _lexical("把 MT-001 的状态改为 blocked"),
        snapshot,
        authorized_entities=(work_item,),
    )

    assert [(item.table_id, item.field_key) for item in result.bound_fields] == [
        (work_items.id, "status")
    ]
    assert [(item.table_id, item.value) for item in result.bound_enum_values] == [
        (work_items.id, "blocked")
    ]
    assert result.ambiguous_candidates == ()


def test_hidden_or_out_of_scope_names_never_become_candidates() -> None:
    uow, _owner, viewer, workspace, _base, _projects, _work_items, employee = _fixture()
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=viewer,
    )

    result = bind_lexical_query(
        _lexical("读取客户密钥和事项编号以及预算字段"), snapshot
    )

    assert result.bound_fields == ()
    assert result.ambiguous_candidates == ()
    assert {item.text for item in result.unresolved_mentions} == {"预算字段"}


def test_duplicate_table_name_is_ambiguous_instead_of_binding_both_tables() -> None:
    uow, owner, _viewer, workspace, base, projects, work_items, employee = _fixture()
    employee.accessible_tables = [str(projects.id), str(work_items.id)]
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )
    duplicate_tables = tuple(
        item.model_copy(update={"name": "交付数据", "aliases": ()})
        for item in snapshot.tables
    )
    values = {
        "version": snapshot.version,
        "workspace_id": workspace.id,
        "employee_id": employee.id,
        "scope_hash": snapshot.scope_hash,
        "tables": duplicate_tables,
    }
    duplicate_snapshot = AuthorizedSchemaSnapshot(
        **values,
        schema_hash=authorized_schema_sha256(**values),
    )

    result = bind_lexical_query(_lexical("查询交付数据"), duplicate_snapshot)

    assert result.bound_tables == ()
    assert len(result.ambiguous_candidates) == 1
    assert result.ambiguous_candidates[0].kind == "table"
    assert set(result.ambiguous_candidates[0].candidate_ids) == {
        str(projects.id),
        str(work_items.id),
    }
    assert set(result.ambiguous_candidates[0].candidate_labels) == {
        "projects:交付数据",
        "work_items:交付数据",
    }


def test_duplicate_entity_label_is_ambiguous_instead_of_first_match_wins() -> None:
    uow, owner, _viewer, workspace, _base, projects, _work_items, employee = _fixture()
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=owner,
    )
    entities = (
        AuthorizedEntitySpec(
            entity_id=uuid4(),
            table_id=projects.id,
            code="PRJ-ATLAS",
            label="同名项目",
            aliases=(),
        ),
        AuthorizedEntitySpec(
            entity_id=uuid4(),
            table_id=projects.id,
            code="PRJ-BEACON",
            label="同名项目",
            aliases=(),
        ),
    )

    result = bind_lexical_query(
        _lexical("比较同名项目"),
        snapshot,
        authorized_entities=entities,
    )

    assert result.bound_entities == ()
    assert len(result.ambiguous_candidates) == 1
    assert result.ambiguous_candidates[0].kind == "entity"
    assert set(result.ambiguous_candidates[0].candidate_ids) == {
        str(item.entity_id) for item in entities
    }
    assert set(result.ambiguous_candidates[0].candidate_labels) == {
        "PRJ-ATLAS:同名项目",
        "PRJ-BEACON:同名项目",
    }
