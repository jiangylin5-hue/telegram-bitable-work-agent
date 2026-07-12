from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes import stage07_draft_employee_hub as draft_employee_hub_routes
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.api.routes.stage06_runtime import get_stage06_runtime_uow
from app.main import create_app
from app.models.stage06_platform import WorkspaceMember
from app.models.stage06_runtime import RecordChangeDraft
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


def test_s5_contact_directory_returns_only_safe_active_contact_projection() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        uow,
        name="S5 Hub",
        owner_user_id=owner.actor_id,
        actor=owner,
    )
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_digital_employee(
        uow,
        base.id,
        name="Operations assistant",
        description="Summarizes and prepares drafts.",
        telegram_alias="ops_private",
        accessible_tables=[str(table.id)],
        accessible_views=[],
        allowed_actions=["summarize", "draft_update"],
        field_policy={"internal": "hidden"},
        confirmation_policy={"draft_update": "required"},
        response_style={"tone": "brief"},
        actor=owner,
    )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.get(
            f"/mini-app/workspaces/{workspace.id}/digital-employee-contacts"
        )

    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": str(workspace.id),
        "contacts": [
            {
                "id": response.json()["contacts"][0]["id"],
                "base_id": str(base.id),
                "name": "Operations assistant",
                "description": "Summarizes and prepares drafts.",
                "status": "active",
                "available_intents": ["summarize", "draft_update"],
            }
        ],
        "next_cursor": None,
        "has_more": False,
    }
    assert "ops_private" not in response.text
    assert "field_policy" not in response.text
    assert "accessible_tables" not in response.text


def test_s5_draft_model_starts_with_terminal_revision_and_audit_reference() -> None:
    assert RecordChangeDraft.__table__.c.version.default.arg == 1
    assert "terminal_audit_event_id" in RecordChangeDraft.__table__.c


def test_s5_draft_read_models_filter_hidden_values_and_metadata() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 drafts", owner_user_id="owner-1", actor=owner)
    viewer = WorkspaceMember(
        id=uuid4(), workspace_id=workspace.id, user_id="viewer-1", role="viewer", status="active"
    )
    uow.add_workspace_member(viewer)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
    create_field(
        uow,
        table.id,
        name="Internal",
        key="internal",
        field_type="text",
        permission_policy={"viewer": "hidden"},
        actor=owner,
    )
    draft = RecordChangeDraft(
        id=uuid4(),
        workspace_id=workspace.id,
        base_id=base.id,
        table_id=table.id,
        record_id=None,
        draft_type="update_record",
        proposed_values={"title": "After", "internal": "secret-after"},
        before_values={"title": {"unsupported": "Before"}, "internal": "secret-before"},
        created_by_type="digital_employee",
        created_by_id="private-employee",
        status="pending_confirmation",
        confirmation_policy={},
        trace_id="private-trace",
        expected_version=7,
        version=1,
    )
    uow.add_record_change_draft(draft)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = "viewer-1"
        listed = client.get(f"/mini-app/bases/{base.id}/drafts")
        detail = client.get(f"/mini-app/drafts/{draft.id}")

    assert listed.status_code == detail.status_code == 200
    assert listed.json()["drafts"] == [{
        "id": str(draft.id), "base_id": str(base.id), "table_id": str(table.id),
        "record_id": None, "draft_type": "update_record", "status": "pending_confirmation", "version": 1,
    }]
    assert detail.json() == {
        "id": str(draft.id), "base_id": str(base.id), "table_id": str(table.id), "record_id": None,
        "draft_type": "update_record", "status": "pending_confirmation", "version": 1,
        "fields": [{"key": "title", "label": "Title", "field_type": "text", "before_value": None, "proposed_value": "After"}],
        "actions": {"can_confirm": False, "can_reject": False}, "terminal_audit_event_id": None,
    }
    assert "secret" not in (listed.text + detail.text)
    assert "private-employee" not in detail.text
    assert "private-trace" not in detail.text


def test_s5_reject_is_versioned_idempotent_and_has_no_record_write() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 reject", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    draft = RecordChangeDraft(
        id=uuid4(), workspace_id=workspace.id, base_id=base.id, table_id=table.id,
        record_id=None, draft_type="update_record", proposed_values={"title": "never-write"},
        before_values=None, created_by_type="digital_employee", created_by_id="private", status="pending_confirmation",
        confirmation_policy={}, trace_id="private-trace", expected_version=1, version=1,
    )
    uow.add_record_change_draft(draft)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        first = client.post(
            f"/mini-app/drafts/{draft.id}/reject", headers={"Idempotency-Key": "s5-reject-1"},
            json={"expected_version": 1},
        )
        replay = client.post(
            f"/mini-app/drafts/{draft.id}/reject", headers={"Idempotency-Key": "s5-reject-1"},
            json={"expected_version": 1},
        )

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["status"] == "rejected"
    assert first.json()["version"] == 2
    assert first.json()["terminal_audit_event_id"]
    assert uow.records == []
    assert "private-trace" not in first.text


def test_s5_confirm_reuses_versioned_record_update_and_safe_receipt() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 confirm", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
    record = create_record(uow, table.id, values={"title": "Before"}, actor=owner)
    draft = RecordChangeDraft(
        id=uuid4(), workspace_id=workspace.id, base_id=base.id, table_id=table.id,
        record_id=record.id, draft_type="update_record", proposed_values={"title": "After"},
        before_values={"title": "Before"}, created_by_type="digital_employee", created_by_id="private",
        status="pending_confirmation", confirmation_policy={}, trace_id="private-trace",
        expected_version=record.version, version=1,
    )
    uow.add_record_change_draft(draft)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.post(
            f"/mini-app/drafts/{draft.id}/confirm", headers={"Idempotency-Key": "s5-confirm-1"},
            json={"expected_version": 1},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["version"] == 2
    assert response.json()["terminal_audit_event_id"]
    assert record.values == {"title": "After"}
    assert record.version == 2
    assert "private-trace" not in response.text


def test_s5_invocation_rejects_generic_action_and_runtime_payloads() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 invoke", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    employee = create_digital_employee(
        uow, base.id, name="Assistant", description="Safe", telegram_alias=None,
        accessible_tables=[str(table.id)], accessible_views=[], allowed_actions=["summarize"], actor=owner,
    )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.post(
            f"/mini-app/digital-employees/{employee.id}/invocations",
            json={"intent": "summarize", "base_id": str(base.id), "action": "query", "runtime_mode": "deterministic"},
        )

    assert response.status_code == 422


def test_s5_summary_invocation_uses_live_runtime_and_drops_generic_runtime_output(
    monkeypatch,
) -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 live invoke", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    employee = create_digital_employee(
        uow, base.id, name="Assistant", description="Safe", telegram_alias=None,
        accessible_tables=[str(table.id)], accessible_views=[], allowed_actions=["summarize"], actor=owner,
    )
    captured: dict[str, object] = {}

    def fake_invoke(*args, **kwargs):
        captured.update(kwargs)
        return {
            "answer": "Only this summary is safe.",
            "records": [{"private": "do-not-forward"}],
            "runtime": {"model_name": "do-not-forward"},
            "trace_id": "do-not-forward",
        }

    monkeypatch.setattr(draft_employee_hub_routes, "invoke_digital_employee", fake_invoke)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.post(
            f"/mini-app/digital-employees/{employee.id}/invocations",
            json={"intent": "summarize", "base_id": str(base.id), "view_id": str(uuid4())},
        )

    assert response.status_code == 200
    assert response.json()["kind"] == "summary"
    assert response.json()["answer"] == "Only this summary is safe."
    assert "do-not-forward" not in response.text
    assert captured["runtime_mode"] == "live_openrouter"


def test_s5_draft_invocation_requires_an_idempotency_key_before_runtime(
    monkeypatch,
) -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 draft key", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    employee = create_digital_employee(
        uow, base.id, name="Assistant", description="Safe", telegram_alias=None,
        accessible_tables=[str(table.id)], accessible_views=[], allowed_actions=["draft_update"], actor=owner,
    )

    def fail_if_invoked(*args, **kwargs):
        raise AssertionError("draft runtime must not run without an idempotency key")

    monkeypatch.setattr(draft_employee_hub_routes, "invoke_digital_employee", fail_if_invoked)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.post(
            f"/mini-app/digital-employees/{employee.id}/invocations",
            json={"intent": "draft_update", "base_id": str(base.id), "view_id": str(uuid4()), "record_id": str(uuid4())},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "idempotency_key_required"


def test_s5_draft_invocation_replays_the_same_safe_draft_pointer_once(
    monkeypatch,
) -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 draft replay", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    employee = create_digital_employee(
        uow, base.id, name="Assistant", description="Safe", telegram_alias=None,
        accessible_tables=[str(table.id)], accessible_views=[], allowed_actions=["draft_update"], actor=owner,
    )
    draft_id = uuid4()
    calls = 0

    def fake_invoke(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {"draft_id": str(draft_id), "status": "pending_confirmation", "trace_id": "do-not-forward"}

    monkeypatch.setattr(draft_employee_hub_routes, "invoke_digital_employee", fake_invoke)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow
    payload = {"intent": "draft_update", "base_id": str(base.id), "view_id": str(uuid4()), "record_id": str(uuid4())}

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        first = client.post(f"/mini-app/digital-employees/{employee.id}/invocations", headers={"Idempotency-Key": "draft-invoke-1"}, json=payload)
        replay = client.post(f"/mini-app/digital-employees/{employee.id}/invocations", headers={"Idempotency-Key": "draft-invoke-1"}, json=payload)

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json() == {"kind": "draft", "answer": None, "citations": [], "draft_id": str(draft_id), "status": "pending_confirmation"}
    assert calls == 1
    assert "do-not-forward" not in first.text


def test_s5_summary_citations_keep_only_currently_visible_record_ids(
    monkeypatch,
) -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 citation", owner_user_id=owner.actor_id, actor=owner)
    base = create_base(uow, workspace.id, name="Operations", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    create_field(uow, table.id, name="Title", key="title", field_type="text", actor=owner)
    record = create_record(uow, table.id, values={"title": "Visible title"}, actor=owner)
    view = create_form_view(
        uow, base.id, table.id, name="Task grid", view_type="grid", config={"fields": ["title"]}, actor=owner,
    )
    employee = create_digital_employee(
        uow, base.id, name="Assistant", description="Safe", telegram_alias=None,
        accessible_tables=[str(table.id)], accessible_views=[str(view.id)], allowed_actions=["summarize"], actor=owner,
    )

    def fake_invoke(*args, **kwargs):
        return {
            "answer": "Safe answer.",
            "citations": [
                {"record_id": str(record.id), "field_keys": ["title", "private"]},
                {"record_id": str(uuid4()), "field_keys": ["private"]},
                {"unexpected": "do-not-forward"},
            ],
        }

    monkeypatch.setattr(draft_employee_hub_routes, "invoke_digital_employee", fake_invoke)
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.post(
            f"/mini-app/digital-employees/{employee.id}/invocations",
            json={"intent": "summarize", "base_id": str(base.id), "view_id": str(view.id)},
        )

    assert response.status_code == 200
    assert response.json()["citations"] == [{"record_id": str(record.id)}]
    assert "field_keys" not in response.text
    assert "do-not-forward" not in response.text


def test_s5_cross_base_summary_context_fails_before_live_runtime() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="S5 cross Base", owner_user_id=owner.actor_id, actor=owner)
    allowed_base = create_base(uow, workspace.id, name="Allowed", actor=owner)
    allowed_table = create_table(uow, allowed_base.id, name="Allowed tasks", key="allowed_tasks", actor=owner)
    allowed_view = create_form_view(
        uow, allowed_base.id, allowed_table.id, name="Allowed grid", view_type="grid", config={"fields": []}, actor=owner,
    )
    other_base = create_base(uow, workspace.id, name="Other", actor=owner)
    other_table = create_table(uow, other_base.id, name="Other tasks", key="other_tasks", actor=owner)
    other_view = create_form_view(
        uow, other_base.id, other_table.id, name="Other grid", view_type="grid", config={"fields": []}, actor=owner,
    )
    employee = create_digital_employee(
        uow, allowed_base.id, name="Assistant", description="Safe", telegram_alias=None,
        accessible_tables=[str(allowed_table.id)], accessible_views=[str(allowed_view.id)], allowed_actions=["summarize"], actor=owner,
    )
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: uow
    app.dependency_overrides[get_stage06_runtime_uow] = lambda: uow

    with TestClient(app) as client:
        client.headers["X-Stage06-User-Id"] = owner.actor_id
        response = client.post(
            f"/mini-app/digital-employees/{employee.id}/invocations",
            json={"intent": "summarize", "base_id": str(allowed_base.id), "view_id": str(other_view.id)},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "digital_employee_scope_denied"
    assert uow.record_change_drafts == []
    assert uow.agent_runs == []
