from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.schemas.stage06_platform import (
    InitializeLookupFieldRequest,
    InitializeRelationFieldRequest,
    RelationCandidatePageResponse,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    PlatformValidationError,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
    initialize_relation_field,
    initialize_lookup_field,
    list_relation_candidates,
    list_view_records,
    safe_table_schema_field,
)


def test_f2_schema_initializer_models_forbid_raw_configuration_and_candidate_page_is_safe() -> None:
    relation = InitializeRelationFieldRequest.model_validate(
        {
            "name": "关联客户",
            "target_table_id": str(uuid4()),
            "required": True,
        }
    )

    assert relation.required is True
    with pytest.raises(ValidationError):
        InitializeLookupFieldRequest.model_validate(
            {
                "name": "金额",
                "source_relation_field_id": str(uuid4()),
                "target_field_id": str(uuid4()),
                "aggregation": "sum",
                "options": {},
            }
        )

    page = RelationCandidatePageResponse.model_validate(
        {
            "field_id": str(uuid4()),
            "records": [{"id": str(uuid4()), "label": "Acme"}],
            "next_cursor": None,
            "has_more": False,
        }
    )

    assert page.model_dump() == {
        "field_id": page.field_id,
        "records": [{"id": page.records[0].id, "label": "Acme"}],
        "next_cursor": None,
        "has_more": False,
    }


def test_relation_initializer_uses_same_base_target_and_appends_only_explicit_views() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1", actor=actor)
    base = create_base(uow, workspace.id, name="Operations", actor=actor)
    source = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    target = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
    explicit_view = create_form_view(
        uow,
        base.id,
        source.id,
        name="Project grid",
        view_type="grid",
        config={"fields": []},
        actor=actor,
    )
    implicit_view = create_form_view(
        uow,
        base.id,
        source.id,
        name="All project fields",
        view_type="grid",
        config={},
        actor=actor,
    )

    result = initialize_relation_field(
        uow,
        source.id,
        name="Related customers",
        target_table_id=target.id,
        required=True,
        actor=actor,
    )

    assert result.field.field_type == "linked_record"
    assert result.field.options == {"target_table_id": str(target.id)}
    assert result.field.required is True
    assert result.affected_view_ids == [explicit_view.id]
    assert explicit_view.config == {"fields": [result.field.key]}
    assert implicit_view.config == {}
    assert safe_table_schema_field(result.field)["options"] == {}
    event = uow.audit_events[-1]
    assert event.event_type == "stage07.relation_field_initialized"
    assert str(target.id) not in str(event.after_state)


def test_relation_initializer_rejects_cross_base_target_before_durable_write() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1", actor=actor)
    source_base = create_base(uow, workspace.id, name="Operations", actor=actor)
    target_base = create_base(uow, workspace.id, name="Finance", actor=actor)
    source = create_table(uow, source_base.id, name="Projects", key="projects", actor=actor)
    target = create_table(uow, target_base.id, name="Customers", key="customers", actor=actor)
    audit_count = len(uow.audit_events)

    with pytest.raises(PlatformValidationError) as error:
        initialize_relation_field(
            uow,
            source.id,
            name="Related customers",
            target_table_id=target.id,
            required=False,
            actor=actor,
        )

    assert error.value.code == "resource_scope_mismatch"
    assert uow.list_fields(source.id) == []
    assert len(uow.audit_events) == audit_count


def test_relation_initializer_endpoint_replays_safe_receipt_and_denies_viewer() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post("/workspaces", json={"name": "Acme", "owner_user_id": "owner-1"}).json()["id"]
        base_id = client.post(f"/workspaces/{workspace_id}/bases", json={"name": "Operations"}).json()["id"]
        source_id = client.post(f"/bases/{base_id}/tables", json={"name": "Projects", "key": "projects"}).json()["id"]
        target_id = client.post(f"/bases/{base_id}/tables", json={"name": "Customers", "key": "customers"}).json()["id"]
        headers = {"Idempotency-Key": "relation-initialization-1"}
        payload = {"name": "Related customers", "target_table_id": target_id, "required": True}

        created = client.post(f"/tables/{source_id}/relation-field-initializations", headers=headers, json=payload)
        replayed = client.post(f"/tables/{source_id}/relation-field-initializations", headers=headers, json=payload)
        conflict = client.post(f"/tables/{source_id}/relation-field-initializations", headers=headers, json={**payload, "name": "Accounts"})
        uow.add_workspace_member(WorkspaceMember(id=uuid4(), workspace_id=UUID(workspace_id), user_id="viewer-1", role="viewer", status="active"))
        client.headers["X-Stage06-User-Id"] = "viewer-1"
        denied = client.post(
            f"/tables/{source_id}/relation-field-initializations",
            headers={"Idempotency-Key": "relation-initialization-denied"},
            json={"name": "Forbidden", "target_table_id": target_id, "required": False},
        )

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json() == created.json()
    assert conflict.status_code == 409
    assert denied.status_code == 403
    assert len(uow.list_fields(UUID(source_id))) == 1
    assert len(uow.idempotency_records) == 1
    assert created.json()["field"]["options"] == {}
    assert target_id not in created.text


def _lookup_fixture(*, target_field_type: str = "number") -> tuple[
    InMemoryStage06PlatformUnitOfWork,
    Actor,
    object,
    object,
    object,
]:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1", actor=actor)
    base = create_base(uow, workspace.id, name="Operations", actor=actor)
    source = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    target = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
    relation = initialize_relation_field(
        uow,
        source.id,
        name="Related customers",
        target_table_id=target.id,
        required=False,
        actor=actor,
    ).field
    target_field = create_field(
        uow,
        target.id,
        name="Amount",
        key="amount",
        field_type=target_field_type,
        options={"choices": ["gold", "silver"]} if target_field_type == "multi_select" else None,
        actor=actor,
    )
    return uow, actor, source, relation, target_field


@pytest.mark.parametrize(
    "aggregation",
    ["values", "count", "count_distinct", "sum", "average", "min", "max"],
)
def test_lookup_initializer_accepts_approved_fixed_aggregations(aggregation: str) -> None:
    uow, actor, source, relation, target_field = _lookup_fixture()

    result = initialize_lookup_field(
        uow,
        source.id,
        name=f"Customer {aggregation}",
        source_relation_field_id=relation.id,
        target_field_id=target_field.id,
        aggregation=aggregation,
        actor=actor,
    )

    assert result.field.field_type == "lookup"
    assert result.field.options == {
        "source_field_id": str(relation.id),
        "target_field_id": str(target_field.id),
        "aggregation": aggregation,
    }
    assert safe_table_schema_field(result.field)["options"] == {}


def test_lookup_initializer_allows_values_for_multi_select_but_rejects_numeric_aggregation_for_text() -> None:
    uow, actor, source, relation, multi_select_field = _lookup_fixture(target_field_type="multi_select")
    result = initialize_lookup_field(
        uow,
        source.id,
        name="Customer segments",
        source_relation_field_id=relation.id,
        target_field_id=multi_select_field.id,
        aggregation="values",
        actor=actor,
    )
    text_field = create_field(
        uow,
        multi_select_field.table_id,
        name="Customer name",
        key="customer_name",
        field_type="text",
        actor=actor,
    )

    with pytest.raises(PlatformValidationError) as error:
        initialize_lookup_field(
            uow,
            source.id,
            name="Customer total",
            source_relation_field_id=relation.id,
            target_field_id=text_field.id,
            aggregation="sum",
            actor=actor,
        )

    assert result.field.field_type == "lookup"
    assert error.value.code == "lookup_target_incompatible"


def test_lookup_initializer_rejects_an_aggregation_outside_the_fixed_enum() -> None:
    uow, actor, source, relation, target_field = _lookup_fixture()

    with pytest.raises(PlatformValidationError) as error:
        initialize_lookup_field(
            uow,
            source.id,
            name="Median amount",
            source_relation_field_id=relation.id,
            target_field_id=target_field.id,
            aggregation="median",
            actor=actor,
        )

    assert error.value.code == "lookup_target_incompatible"
    assert [field.field_type for field in uow.list_fields(source.id)] == ["linked_record"]


def test_lookup_initializer_resolves_a_legacy_key_config_for_one_nested_level() -> None:
    uow, actor, source, relation, target_field = _lookup_fixture()
    target_relation = initialize_relation_field(
        uow,
        target_field.table_id,
        name="Related customers",
        target_table_id=target_field.table_id,
        required=False,
        actor=actor,
    ).field
    legacy_lookup = create_field(
        uow,
        target_field.table_id,
        name="Legacy amount",
        key="legacy_amount",
        field_type="lookup",
        options={
            "source_field_key": target_relation.key,
            "target_field_key": target_field.key,
        },
        actor=actor,
    )

    result = initialize_lookup_field(
        uow,
        source.id,
        name="Nested legacy amount",
        source_relation_field_id=relation.id,
        target_field_id=legacy_lookup.id,
        aggregation="values",
        actor=actor,
    )

    assert result.field.field_type == "lookup"
    assert result.field.options["target_field_id"] == str(legacy_lookup.id)


def test_lookup_initializer_rejects_non_relation_source_cross_base_relation_and_hidden_target_field() -> None:
    uow, actor, source, relation, target_field = _lookup_fixture()
    non_relation = create_field(uow, source.id, name="Title", key="title", field_type="text", actor=actor)
    hidden_target = create_field(
        uow,
        target_field.table_id,
        name="Private amount",
        key="private_amount",
        field_type="number",
        permission_policy={"viewer": "hidden"},
        actor=actor,
    )
    viewer = Actor(actor_type="user", actor_id="viewer-1", role="viewer")
    cross_base = create_base(uow, uow.get_base(source.base_id).workspace_id, name="Finance", actor=actor)
    cross_table = create_table(uow, cross_base.id, name="Invoices", key="invoices", actor=actor)
    cross_relation = create_field(
        uow,
        source.id,
        name="Cross base",
        key="cross_base",
        field_type="linked_record",
        options={"target_table_id": str(cross_table.id)},
        actor=actor,
    )

    with pytest.raises(PlatformValidationError) as source_error:
        initialize_lookup_field(
            uow,
            source.id,
            name="Broken source",
            source_relation_field_id=non_relation.id,
            target_field_id=target_field.id,
            aggregation="values",
            actor=actor,
        )
    with pytest.raises(PlatformValidationError) as hidden_error:
        initialize_lookup_field(
            uow,
            source.id,
            name="Hidden target",
            source_relation_field_id=relation.id,
            target_field_id=hidden_target.id,
            aggregation="values",
            actor=viewer,
        )
    with pytest.raises(PlatformValidationError) as scope_error:
        initialize_lookup_field(
            uow,
            source.id,
            name="Cross base target",
            source_relation_field_id=cross_relation.id,
            target_field_id=target_field.id,
            aggregation="values",
            actor=actor,
        )

    assert source_error.value.code == "lookup_source_not_relation"
    assert hidden_error.value.code == "permission_denied"
    assert scope_error.value.code == "resource_scope_mismatch"


def test_lookup_initializer_rejects_cycle_and_third_lookup_level() -> None:
    uow, actor, source, relation, target_field = _lookup_fixture()
    target_relation = initialize_relation_field(
        uow,
        target_field.table_id,
        name="Related customers",
        target_table_id=target_field.table_id,
        required=False,
        actor=actor,
    ).field
    first = create_field(
        uow,
        target_field.table_id,
        name="First lookup",
        key="first_lookup",
        field_type="lookup",
        options={
            "source_field_id": str(target_relation.id),
            "target_field_id": str(target_field.id),
            "aggregation": "values",
        },
        actor=actor,
    )
    second = create_field(
        uow,
        target_field.table_id,
        name="Second lookup",
        key="second_lookup",
        field_type="lookup",
        options={
            "source_field_id": str(target_relation.id),
            "target_field_id": str(first.id),
            "aggregation": "values",
        },
        actor=actor,
    )

    with pytest.raises(PlatformValidationError) as depth_error:
        initialize_lookup_field(
            uow,
            source.id,
            name="Third lookup",
            source_relation_field_id=relation.id,
            target_field_id=second.id,
            aggregation="values",
            actor=actor,
        )

    first.options = {
        "source_field_id": str(target_relation.id),
        "target_field_id": str(second.id),
        "aggregation": "values",
    }
    with pytest.raises(PlatformValidationError) as cycle_error:
        initialize_lookup_field(
            uow,
            source.id,
            name="Cyclic lookup",
            source_relation_field_id=relation.id,
            target_field_id=first.id,
            aggregation="values",
            actor=actor,
        )

    assert depth_error.value.code == "lookup_depth_exceeded"
    assert cycle_error.value.code == "lookup_dependency_cycle"


def test_lookup_initializer_endpoint_replays_a_redacted_receipt() -> None:
    uow, actor, source, relation, target_field = _lookup_fixture()
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    payload = {
        "name": "Customer total",
        "source_relation_field_id": str(relation.id),
        "target_field_id": str(target_field.id),
        "aggregation": "sum",
    }

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = actor.actor_id
        created = client.post(
            f"/tables/{source.id}/lookup-field-initializations",
            headers={"Idempotency-Key": "lookup-initialization-1"},
            json=payload,
        )
        replayed = client.post(
            f"/tables/{source.id}/lookup-field-initializations",
            headers={"Idempotency-Key": "lookup-initialization-1"},
            json=payload,
        )

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json() == created.json()
    assert created.json()["field"]["field_type"] == "lookup"
    assert created.json()["field"]["options"] == {}
    assert str(relation.id) not in created.text
    assert str(target_field.id) not in created.text


def test_relation_candidates_and_safe_relation_projection_use_only_readable_labels() -> None:
    uow, owner, source, relation, target_field = _lookup_fixture()
    target = uow.get_table(target_field.table_id)
    assert target is not None
    label_field = create_field(
        uow,
        target.id,
        name="Customer name",
        key="customer_name",
        field_type="text",
        actor=owner,
    )
    secret_field = create_field(
        uow,
        target.id,
        name="Secret",
        key="secret",
        field_type="text",
        permission_policy={"viewer": "hidden"},
        actor=owner,
    )
    target.primary_field_id = label_field.id
    first = create_record(
        uow,
        target.id,
        values={label_field.key: "Acme", secret_field.key: "must-not-leak"},
        actor=owner,
    )
    second = create_record(
        uow,
        target.id,
        values={label_field.key: "Acorn"},
        actor=owner,
    )
    source_record = create_record(
        uow,
        source.id,
        values={relation.key: [str(first.id), str(second.id)]},
        actor=owner,
    )
    source_base = uow.get_base(source.base_id)
    assert source_base is not None
    view = create_form_view(
        uow,
        source_base.id,
        source.id,
        name="Projects",
        view_type="grid",
        config={"fields": [relation.key]},
        actor=owner,
    )
    viewer = Actor(actor_type="user", actor_id="viewer-1", role="viewer")

    page = list_relation_candidates(
        uow,
        relation.id,
        actor=viewer,
        query="ac",
        cursor=None,
        limit=1,
    )
    projected = list_view_records(uow, view.id, actor=viewer, limit=50, cursor=None)
    expected_candidate = min((first, second), key=lambda item: str(item.id))

    assert page["field_id"] == str(relation.id)
    assert page["records"] == [{
        "id": str(expected_candidate.id),
        "label": "Acme" if expected_candidate.id == first.id else "Acorn",
    }]
    assert page["next_cursor"] is not None
    assert page["has_more"] is True
    assert projected["records"] == [
        {
            "id": str(source_record.id),
            "fields": {
                relation.key: [
                    {"id": str(first.id), "label": "Acme"},
                    {"id": str(second.id), "label": "Acorn"},
                ]
            },
        }
    ]
    assert "must-not-leak" not in repr(page)
    assert "must-not-leak" not in repr(projected)


def test_relation_candidate_endpoint_returns_only_safe_records() -> None:
    uow, owner, source, relation, target_field = _lookup_fixture()
    target = uow.get_table(target_field.table_id)
    assert target is not None
    label_field = create_field(
        uow,
        target.id,
        name="Customer name",
        key="customer_name",
        field_type="text",
        actor=owner,
    )
    target.primary_field_id = label_field.id
    target_record = create_record(
        uow,
        target.id,
        values={label_field.key: "Acme"},
        actor=owner,
    )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.get(f"/fields/{relation.id}/relation-candidates?q=ac")

    assert response.status_code == 200
    assert response.json() == {
        "field_id": str(relation.id),
        "records": [{"id": str(target_record.id), "label": "Acme"}],
        "next_cursor": None,
        "has_more": False,
    }
    assert "target_table_id" not in response.text
    assert "permission_policy" not in response.text
