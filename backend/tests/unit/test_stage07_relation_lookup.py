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
    create_form_view,
    create_table,
    create_workspace,
    initialize_relation_field,
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
