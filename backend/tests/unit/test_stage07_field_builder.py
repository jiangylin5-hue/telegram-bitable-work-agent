from fastapi.testclient import TestClient
import pytest

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_form_view,
    create_table,
    create_workspace,
    initialize_field,
    PlatformValidationError,
)


def test_canvas_schema_projects_only_safe_field_metadata() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        base_id = client.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "Operations"},
        ).json()["id"]
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Projects", "key": "projects"},
        ).json()["id"]
        field_response = client.post(
            f"/tables/{table_id}/fields",
            json={
                "name": "Stage",
                "key": "stage",
                "field_type": "status",
                "required": True,
                "options": {
                    "choices": ["new", "active"],
                    "internal_rule": "must-not-leak",
                },
                "permission_policy": {"viewer": "hidden"},
            },
        )

        schema_response = client.get(f"/tables/{table_id}/schema")

    assert field_response.status_code == 200
    assert schema_response.status_code == 200
    assert schema_response.json()["fields"] == [
        {
            "id": field_response.json()["id"],
            "table_id": table_id,
            "name": "Stage",
            "key": "stage",
            "field_type": "status",
            "required": True,
            "options": {"choices": ["new", "active"]},
            "order_index": 0,
        }
    ]
    assert "permission_policy" not in schema_response.text
    assert "internal_rule" not in schema_response.text


def test_initialize_field_generates_safe_field_and_adds_it_to_same_table_views() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1", actor=actor)
    base = create_base(uow, workspace.id, name="Operations", actor=actor)
    table = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="All projects",
        view_type="grid",
        config={"fields": []},
        actor=actor,
    )

    result = initialize_field(
        uow,
        table.id,
        name="Stage",
        field_type="status",
        required=True,
        choices=["new", "active"],
        actor=actor,
    )

    assert result.field.name == "Stage"
    assert result.field.key.startswith("fld_")
    assert result.field.field_type == "status"
    assert result.field.required is True
    assert result.field.options == {"choices": ["new", "active"]}
    assert result.field.permission_policy == {}
    assert result.field.order_index == 0
    assert result.affected_view_ids == [view.id]
    assert view.config == {"fields": [result.field.key]}


@pytest.mark.parametrize(
    ("field_type", "choices", "expected_code"),
    [
        ("json", None, "unsupported_field_type"),
        ("linked_record", None, "unsupported_field_type"),
        ("text", ["unexpected"], "unexpected_field_choices"),
        ("status", None, "invalid_field_choices"),
        ("status", ["new", " NEW "], "invalid_field_choices"),
    ],
)
def test_initialize_field_rejects_types_or_choices_outside_f1_contract(
    field_type: str,
    choices: list[str] | None,
    expected_code: str,
) -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1", actor=actor)
    base = create_base(uow, workspace.id, name="Operations", actor=actor)
    table = create_table(uow, base.id, name="Projects", key="projects", actor=actor)

    with pytest.raises(PlatformValidationError) as error:
        initialize_field(
            uow,
            table.id,
            name="Stage",
            field_type=field_type,
            required=False,
            choices=choices,
            actor=actor,
        )

    assert error.value.code == expected_code
    assert uow.list_fields(table.id) == []


def test_initialize_field_rejects_normalized_duplicate_names() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1", actor=actor)
    base = create_base(uow, workspace.id, name="Operations", actor=actor)
    table = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    initialize_field(
        uow,
        table.id,
        name="Stage",
        field_type="text",
        required=False,
        choices=None,
        actor=actor,
    )

    with pytest.raises(PlatformValidationError) as error:
        initialize_field(
            uow,
            table.id,
            name=" stage ",
            field_type="text",
            required=False,
            choices=None,
            actor=actor,
        )

    assert error.value.code == "duplicate_field_name"
    assert len(uow.list_fields(table.id)) == 1


def test_initialize_field_only_updates_explicit_views_and_emits_safe_audit() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1", actor=actor)
    base = create_base(uow, workspace.id, name="Operations", actor=actor)
    table = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    explicit_view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Visible fields",
        view_type="grid",
        config={"fields": []},
        actor=actor,
    )
    implicit_view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Implicit fields",
        view_type="grid",
        config={},
        actor=actor,
    )

    first = initialize_field(
        uow,
        table.id,
        name="Stage",
        field_type="status",
        required=True,
        choices=["new", "active"],
        actor=actor,
    )
    second = initialize_field(
        uow,
        table.id,
        name="Priority",
        field_type="text",
        required=False,
        choices=None,
        actor=actor,
    )

    assert (first.field.order_index, second.field.order_index) == (0, 1)
    assert explicit_view.config == {"fields": [first.field.key, second.field.key]}
    assert implicit_view.config == {}
    assert second.affected_view_ids == [explicit_view.id]
    event = uow.audit_events[-1]
    assert event.event_type == "stage07.field_initialized"
    assert event.after_state == {
        "table_id": str(table.id),
        "field_key": second.field.key,
        "field_type": "text",
        "required": False,
        "order_index": 1,
        "affected_view_ids": [str(explicit_view.id)],
    }
