from fastapi.testclient import TestClient
import pytest
from uuid import UUID, uuid4

from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_form_view,
    create_field,
    create_record,
    create_table,
    create_workspace,
    get_create_form,
    initialize_field,
    PlatformValidationError,
    update_record,
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


def test_field_initialization_endpoint_replays_same_key_and_rejects_payload_change() -> None:
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
        headers = {"Idempotency-Key": "field-initialization-1"}
        payload = {
            "name": "Stage",
            "field_type": "status",
            "required": False,
            "choices": ["new", "active"],
        }

        created = client.post(
            f"/tables/{table_id}/field-initializations",
            headers=headers,
            json=payload,
        )
        replayed = client.post(
            f"/tables/{table_id}/field-initializations",
            headers=headers,
            json=payload,
        )
        conflict = client.post(
            f"/tables/{table_id}/field-initializations",
            headers=headers,
            json={**payload, "name": "Priority"},
        )

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json() == created.json()
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    assert len(uow.list_fields(UUID(table_id))) == 1
    assert len(uow.idempotency_records) == 1
    assert set(created.json()) == {"field", "affected_view_ids"}
    assert set(created.json()["field"]) == {
        "id",
        "table_id",
        "name",
        "key",
        "field_type",
        "required",
        "options",
        "order_index",
    }
    assert "permission_policy" not in created.text
    assert "config" not in created.text


def test_field_initialization_endpoint_denies_viewer_and_forbids_raw_keys() -> None:
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
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(),
                workspace_id=UUID(workspace_id),
                user_id="viewer-1",
                role="viewer",
                status="active",
            )
        )
        client.headers["X-Stage06-User-Id"] = "viewer-1"
        denied = client.post(
            f"/tables/{table_id}/field-initializations",
            headers={"Idempotency-Key": "field-initialization-denied"},
            json={"name": "Stage", "field_type": "text", "required": False},
        )
        client.headers["X-Stage06-User-Id"] = "owner-1"
        rejected = client.post(
            f"/tables/{table_id}/field-initializations",
            headers={"Idempotency-Key": "field-initialization-extra"},
            json={
                "name": "Stage",
                "field_type": "text",
                "required": False,
                "key": "browser-controlled-key",
            },
        )

    assert denied.status_code == 403
    assert rejected.status_code == 422
    assert uow.list_fields(UUID(table_id)) == []
    assert uow.idempotency_records == []


def test_field_initialization_endpoint_denies_a_table_in_another_workspace() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-2"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Other workspace", "owner_user_id": "owner-2"},
        ).json()["id"]
        base_id = client.post(
            f"/workspaces/{workspace_id}/bases",
            json={"name": "Other operations"},
        ).json()["id"]
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Other projects", "key": "other-projects"},
        ).json()["id"]
        client.headers["X-Stage06-User-Id"] = "owner-1"
        denied = client.post(
            f"/tables/{table_id}/field-initializations",
            headers={"Idempotency-Key": "field-initialization-cross-workspace"},
            json={"name": "Stage", "field_type": "text", "required": False},
        )

    assert denied.status_code == 403
    assert uow.list_fields(UUID(table_id)) == []
    assert uow.idempotency_records == []


def test_field_initialization_rolls_back_field_audit_and_idempotency_on_view_failure() -> None:
    class SnapshotSession:
        def __init__(self, uow: InMemoryStage06PlatformUnitOfWork) -> None:
            self.uow = uow
            self.snapshot()

        def add(self, value: object) -> None:
            self.uow.add(value)

        def commit(self) -> None:
            self.snapshot()

        def rollback(self) -> None:
            self.uow.fields = list(self.fields)
            self.uow.audit_events = list(self.audit_events)
            self.uow.idempotency_records = list(self.idempotency_records)
            for view, config in self.view_configs:
                view.config = config

        def snapshot(self) -> None:
            self.fields = list(self.uow.fields)
            self.audit_events = list(self.uow.audit_events)
            self.idempotency_records = list(self.uow.idempotency_records)
            self.view_configs = [
                (view, None if view.config is None else dict(view.config))
                for view in self.uow.views
            ]

    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    uow.session = SnapshotSession(uow)
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app, raise_server_exceptions=False) as client:
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
        client.post(
            f"/bases/{base_id}/views",
            json={
                "table_id": table_id,
                "name": "Broken view",
                "view_type": "grid",
                "config": {"fields": []},
            },
        )
        uow.views[0].config = None
        uow.session.snapshot()
        audit_count = len(uow.audit_events)

        failed = client.post(
            f"/tables/{table_id}/field-initializations",
            headers={"Idempotency-Key": "field-initialization-rollback"},
            json={"name": "Stage", "field_type": "text", "required": False},
        )

    assert failed.status_code == 500
    assert uow.list_fields(UUID(table_id)) == []
    assert len(uow.audit_events) == audit_count
    assert uow.idempotency_records == []
    assert uow.views[0].config is None


def test_configured_choice_fields_validate_create_update_and_keep_legacy_status_compatible() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1", actor=actor)
    base = create_base(uow, workspace.id, name="Operations", actor=actor)
    table = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    tags = initialize_field(
        uow,
        table.id,
        name="Tags",
        field_type="multi_select",
        required=True,
        choices=["vip", "trial"],
        actor=actor,
    ).field
    legacy_status = create_field(
        uow,
        table.id,
        name="Legacy status",
        key="legacy_status",
        field_type="status",
        actor=actor,
    )

    record = create_record(
        uow,
        table.id,
        values={tags.key: ["vip", "trial"], legacy_status.key: "historic-value"},
        actor=actor,
    )
    assert record.values == {
        tags.key: ["vip", "trial"],
        legacy_status.key: "historic-value",
    }

    for invalid_tags in (["vip", "unknown"], ["vip", "vip"]):
        with pytest.raises(PlatformValidationError) as error:
            create_record(
                uow,
                table.id,
                values={tags.key: invalid_tags},
                actor=actor,
            )
        assert error.value.code == "invalid_field_choice"

    with pytest.raises(PlatformValidationError) as error:
        update_record(
            uow,
            record.id,
            values={tags.key: ["unknown"]},
            expected_version=record.version,
            actor=actor,
        )

    assert error.value.code == "invalid_field_choice"
    assert record.values[tags.key] == ["vip", "trial"]
    assert record.version == 1
    assert get_create_form(uow, table.id, actor=actor) == {
        "table_id": str(table.id),
        "can_create": True,
        "fields": [
            {
                "key": tags.key,
                "name": "Tags",
                "field_type": "multi_select",
                "required": True,
                "options": {"choices": ["vip", "trial"]},
                "order_index": 0,
            },
            {
                "key": "legacy_status",
                "name": "Legacy status",
                "field_type": "status",
                "required": False,
                "options": {},
                "order_index": 1,
            },
        ],
    }
