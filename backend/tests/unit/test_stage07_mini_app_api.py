from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api import deps
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.main import create_app
from app.models.stage06_platform import Stage06TelegramBinding, WorkspaceMember
from app.models.stage06_runtime import RecordChangeDraft
from app.models.stage08_group_context import Stage08GroupBusinessContextBinding
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import InMemoryStage06PlatformUnitOfWork
from app.services.stage06_platform import (
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage09_browser_handoffs import issue_browser_handoff


def test_mini_app_bootstrap_only_returns_active_memberships_for_identity() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[deps.get_stage06_identity_uow] = lambda: uow

    with TestClient(app, base_url="https://testserver") as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Owner workspace", "owner_user_id": "owner-1"},
        ).json()["id"]
        client.headers["X-Stage06-User-Id"] = "owner-2"
        other_workspace_id = client.post(
            "/workspaces",
            json={"name": "Other workspace", "owner_user_id": "owner-2"},
        ).json()["id"]
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(),
                workspace_id=UUID(other_workspace_id),
                user_id="owner-1",
                role="viewer",
                status="inactive",
            )
        )

        client.headers["X-Stage06-User-Id"] = "owner-1"
        response = client.get("/mini-app/bootstrap")

    assert response.status_code == 200
    assert response.json() == {
        "identity": {"user_id": "owner-1", "source": "development_header"},
        "workspaces": [
            {
                "id": workspace_id,
                "name": "Owner workspace",
                "slug": "owner-workspace",
                "role": "owner",
                "capabilities": {
                    "can_read_bases": True,
                    "can_manage_workspace": True,
                    "can_manage_schema": True,
                    "can_manage_digital_employees": True,
                    "can_review_drafts": True,
                },
            }
        ],
    }


def test_browser_handoff_exchange_sets_secure_cookie_and_bootstrap_uses_it() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[deps.get_stage06_identity_uow] = lambda: uow
    ticket = issue_browser_handoff(
        uow,
        Stage06RequestIdentity(
            user_id="owner-1",
            source="telegram_binding",
            telegram_user_id="telegram-owner-1",
        ),
        datetime.now(UTC),
    )

    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/mini-app/browser-handoff-exchanges",
            json={"ticket": ticket},
        )
        bootstrap = client.get("/mini-app/bootstrap")

    assert response.status_code == 204
    assert "Secure" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert "Path=/" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert ticket not in response.text
    assert bootstrap.status_code == 200
    assert bootstrap.json()["identity"] == {
        "user_id": "owner-1",
        "source": "browser_session",
    }


def test_workspace_home_returns_safe_base_and_draft_queue_models() -> None:
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
            json={"name": "Operations", "description": "Internal workspace"},
        ).json()["id"]
        draft_id = uuid4()
        uow.add_record_change_draft(
            RecordChangeDraft(
                id=draft_id,
                workspace_id=UUID(workspace_id),
                base_id=UUID(base_id),
                table_id=uuid4(),
                record_id=None,
                draft_type="record_update",
                proposed_values={"sensitive": "must not reach home"},
                before_values={"sensitive": "must not reach home"},
                created_by_type="agent",
                created_by_id="agent-1",
                status="pending_confirmation",
                confirmation_policy={},
                trace_id="trace-1",
                expected_version=1,
            )
        )

        response = client.get(f"/workspaces/{workspace_id}/home")

    assert response.status_code == 200
    body = response.json()
    assert body["recent_bases"] == [
        {
            "id": base_id,
            "name": "Operations",
            "source_type": "blank",
        }
    ]
    assert body["queue"] == [
        {
            "id": str(draft_id),
            "kind": "record_change_draft",
            "title": "待确认变更",
            "status": "pending_confirmation",
            "destination": {"base_id": base_id, "draft_id": str(draft_id)},
            "action_availability": {"can_confirm": True, "can_reject": True},
        }
    ]
    assert "sensitive" not in response.text


def test_workspace_home_returns_authorized_employee_group_customer_project_index() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="Acme",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    member = uow.list_workspace_members(workspace.id)[0]
    base = create_base(uow, workspace.id, name="CRM", actor=actor)
    customers = create_table(uow, base.id, name="Customers", key="customers", actor=actor)
    projects = create_table(uow, base.id, name="Projects", key="projects", actor=actor)
    create_field(uow, customers.id, name="Name", key="name", field_type="text", actor=actor)
    create_field(uow, projects.id, name="Title", key="title", field_type="text", actor=actor)
    customer = create_record(uow, customers.id, values={"name": "Acme Co"}, actor=actor)
    project = create_record(uow, projects.id, values={"title": "Renewal"}, actor=actor)
    employee = create_digital_employee(
        uow,
        base.id,
        name="Customer Success",
        description="Controlled customer follow-up",
        telegram_alias="cs",
        accessible_tables=[str(customers.id), str(projects.id)],
        accessible_views=[],
        allowed_actions=["query", "summarize", "draft_update"],
        actor=actor,
    )
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace.id,
        workspace_member_id=member.id,
        telegram_chat_id="-1001234567",
        telegram_user_id="telegram-owner-1",
        binding_type="chat_user",
        default_base_id=base.id,
        default_digital_employee_id=employee.id,
        scope_policy={},
        status="active",
    )
    uow.add_telegram_binding(binding)
    uow.add_group_business_context_binding(
        Stage08GroupBusinessContextBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            telegram_binding_id=binding.id,
            customer_record_id=customer.id,
            project_record_id=project.id,
            mapping_version=1,
            status="active",
        )
    )

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = actor.actor_id
        response = client.get(f"/workspaces/{workspace.id}/home")
        second_binding = Stage06TelegramBinding(
            id=uuid4(),
            workspace_id=workspace.id,
            workspace_member_id=member.id,
            telegram_chat_id="-1007654321",
            telegram_user_id="telegram-owner-1",
            binding_type="chat_user",
            default_base_id=base.id,
            default_digital_employee_id=employee.id,
            scope_policy={},
            status="active",
        )
        uow.add_telegram_binding(second_binding)
        uow.add_group_business_context_binding(
            Stage08GroupBusinessContextBinding(
                id=uuid4(),
                workspace_id=workspace.id,
                telegram_binding_id=second_binding.id,
                customer_record_id=customer.id,
                project_record_id=project.id,
                mapping_version=1,
                status="active",
            )
        )
        ambiguous_response = client.get(f"/workspaces/{workspace.id}/home")

    assert response.status_code == 200
    assert response.json()["business_context_relations"] == [
        {
            "employee": {
                "id": str(employee.id),
                "name": "Customer Success",
                "base_id": str(base.id),
                "base_name": "CRM",
            },
            "group": {"id": f"group_context:{binding.id}", "label": "已授权群聊 1"},
            "customer": {
                "id": str(customer.id),
                "base_id": str(base.id),
                "label": "Acme Co",
            },
            "project": {
                "id": str(project.id),
                "base_id": str(base.id),
                "label": "Renewal",
            },
            "mapping_version": 1,
        }
    ]
    assert "-1001234567" not in response.text
    assert "telegram-owner-1" not in response.text
    assert ambiguous_response.status_code == 200
    assert ambiguous_response.json()["business_context_relations"] == []


def test_workspace_home_denies_non_members() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post(
            "/workspaces",
            json={"name": "Acme", "owner_user_id": "owner-1"},
        ).json()["id"]
        client.headers["X-Stage06-User-Id"] = "outsider-1"
        response = client.get(f"/workspaces/{workspace_id}/home")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "stage06_membership_required"


def test_base_canvas_navigation_lists_only_authorized_safe_summaries() -> None:
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
            json={"name": "Operations", "description": "must not be listed"},
        ).json()["id"]
        table_id = client.post(
            f"/bases/{base_id}/tables",
            json={"name": "Projects", "key": "projects"},
        ).json()["id"]
        view_id = client.post(
            f"/bases/{base_id}/views",
            json={
                "table_id": table_id,
                "name": "Project Grid",
                "view_type": "grid",
                "config": {"fields": ["hidden-from-navigation"]},
                "permission_policy": {"viewer": "hidden"},
            },
        ).json()["id"]

        bases_response = client.get(f"/workspaces/{workspace_id}/bases")
        tables_response = client.get(f"/bases/{base_id}/tables")
        views_response = client.get(f"/bases/{base_id}/views")

    assert bases_response.status_code == 200
    assert bases_response.json() == {
        "bases": [
            {
                "id": base_id,
                "name": "Operations",
                "source_type": "blank",
                "status": "active",
            }
        ]
    }
    assert tables_response.status_code == 200
    assert tables_response.json() == {
        "tables": [
            {
                "id": table_id,
                "base_id": base_id,
                "name": "Projects",
                "key": "projects",
                "status": "active",
            }
        ]
    }
    assert views_response.status_code == 200
    assert views_response.json() == {
        "views": [
            {
                "id": view_id,
                "base_id": base_id,
                "table_id": table_id,
                "name": "Project Grid",
                "view_type": "grid",
                "status": "active",
            }
        ]
    }
    assert "hidden-from-navigation" not in views_response.text
    assert "permission_policy" not in views_response.text


def test_base_canvas_navigation_denies_cross_workspace_access() -> None:
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
        client.headers["X-Stage06-User-Id"] = "outsider-1"
        bases_response = client.get(f"/workspaces/{workspace_id}/bases")
        tables_response = client.get(f"/bases/{base_id}/tables")
        views_response = client.get(f"/bases/{base_id}/views")

    assert bases_response.status_code == 403
    assert tables_response.status_code == 403
    assert views_response.status_code == 403


def test_view_presentation_record_detail_and_schema_hide_inaccessible_fields() -> None:
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
        client.post(
            f"/tables/{table_id}/fields",
            json={"name": "Name", "key": "name", "field_type": "text"},
        )
        client.post(
            f"/tables/{table_id}/fields",
            json={
                "name": "Internal", "key": "internal", "field_type": "text",
                "permission_policy": {"viewer": "hidden"},
            },
        )
        client.post(
            f"/tables/{table_id}/fields",
            json={"name": "Due", "key": "due", "field_type": "date"},
        )
        record_id = client.post(
            f"/tables/{table_id}/records",
            json={"values": {"name": "Ada", "internal": "secret", "due": "2026-07-10"}},
        ).json()["id"]
        view_id = client.post(
            f"/bases/{base_id}/views",
            json={
                "table_id": table_id,
                "name": "Project Calendar",
                "view_type": "calendar",
                "config": {
                    "fields": ["name", "internal", "due"],
                    "group_by_field_key": "internal",
                    "date_field_key": "due",
                },
            },
        ).json()["id"]
        uow.add_workspace_member(
            WorkspaceMember(
                id=uuid4(), workspace_id=UUID(workspace_id), user_id="viewer-1",
                role="viewer", status="active",
            )
        )

        client.headers["X-Stage06-User-Id"] = "viewer-1"
        schema_response = client.get(f"/tables/{table_id}/schema")
        presentation_response = client.get(f"/views/{view_id}/presentation")
        record_response = client.get(f"/records/{record_id}")

    assert schema_response.status_code == 200
    assert [field["key"] for field in schema_response.json()["fields"]] == ["name", "due"]
    assert presentation_response.status_code == 200
    assert presentation_response.json() == {
        "view_id": view_id,
        "table_id": table_id,
        "view_type": "calendar",
        "visible_field_keys": ["name", "due"],
        "group_by_field_key": None,
        "date_field_key": "due",
        "form_field_keys": ["name", "due"],
    }
    assert record_response.status_code == 200
    assert record_response.json()["values"] == {"name": "Ada", "due": "2026-07-10"}
    assert "secret" not in record_response.text


def test_create_form_returns_only_server_writable_fields_without_policy() -> None:
    app = create_app()
    uow = InMemoryStage06PlatformUnitOfWork()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "owner-1"
        workspace_id = client.post("/workspaces", json={"name": "Acme", "owner_user_id": "owner-1"}).json()["id"]
        base_id = client.post(f"/workspaces/{workspace_id}/bases", json={"name": "Operations"}).json()["id"]
        table_id = client.post(f"/bases/{base_id}/tables", json={"name": "Projects", "key": "projects"}).json()["id"]
        title_field = client.post(f"/tables/{table_id}/fields", json={"name": "Title", "key": "title", "field_type": "text", "required": True, "permission_policy": {"operator": "write"}}).json()
        status_field = client.post(f"/tables/{table_id}/fields", json={"name": "Status", "key": "status", "field_type": "status", "options": {"choices": ["new", "active"], "internal_rule": "must-not-leak"}, "permission_policy": {"operator": "write"}}).json()
        client.post(f"/tables/{table_id}/fields", json={"name": "Related accounts", "key": "accounts", "field_type": "linked_record", "required": True, "options": {"target_table_id": str(uuid4())}, "permission_policy": {"operator": "write"}})
        client.post(f"/tables/{table_id}/fields", json={"name": "Internal", "key": "internal", "field_type": "text", "permission_policy": {"operator": "read"}})
        uow.add_workspace_member(WorkspaceMember(id=uuid4(), workspace_id=UUID(workspace_id), user_id="operator-1", role="operator", status="active"))
        client.headers["X-Stage06-User-Id"] = "operator-1"
        response = client.get(f"/tables/{table_id}/create-form")

    assert response.status_code == 200
    assert response.json()["table_id"] == table_id
    assert response.json()["can_create"] is False
    assert response.json()["fields"] == [
        {"id": title_field["id"], "key": "title", "name": "Title", "field_type": "text", "required": True, "options": {}, "order_index": 0},
        {"id": status_field["id"], "key": "status", "name": "Status", "field_type": "status", "required": False, "options": {"choices": ["new", "active"]}, "order_index": 1},
    ]
    assert "permission_policy" not in response.text
    assert "internal" not in response.text
    assert "accounts" not in response.text


def test_create_form_and_record_api_support_configured_multi_select_choices() -> None:
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
        field = client.post(
            f"/tables/{table_id}/field-initializations",
            headers={"Idempotency-Key": "multi-select-field"},
            json={
                "name": "Tags",
                "field_type": "multi_select",
                "required": True,
                "choices": ["vip", "trial"],
            },
        ).json()["field"]
        form = client.get(f"/tables/{table_id}/create-form")
        created = client.post(
            f"/tables/{table_id}/records",
            json={"values": {field["key"]: ["vip", "trial"]}},
        )
        rejected = client.post(
            f"/tables/{table_id}/records",
            json={"values": {field["key"]: ["vip", "unknown"]}},
        )

    assert form.status_code == 200
    assert form.json() == {
        "table_id": table_id,
        "can_create": True,
        "fields": [
                {
                    "id": field["id"],
                    "key": field["key"],
                "name": "Tags",
                "field_type": "multi_select",
                "required": True,
                "options": {"choices": ["vip", "trial"]},
                "order_index": 0,
            }
        ],
    }
    assert created.status_code == 200
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "invalid_field_choice"
