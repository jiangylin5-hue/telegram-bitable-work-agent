from dataclasses import replace
from datetime import UTC, datetime, timedelta
import base64
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes.agent_runs import (
    get_agent_event_runtime_uow,
    get_stage12_action_repository,
)
import app.api.routes.agent_runs as agent_run_routes
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.agent_event_runtime import AgentPrivateInput, AgentWorkflowRun
from app.schemas.stage12_action_runtime import (
    ActionPrivatePayloadV1,
    ActionSlotControlV1,
)
from app.services.agent_event_runtime import InMemoryAgentEventRuntimeUnitOfWork
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.agent_field_policy_v2 import build_stage12_action_scope_hash
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.permissions import Actor
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_table,
    create_workspace,
)
from app.services.stage12_action_materialization import materialize_action_slot
from app.services.stage12_action_private_payload import (
    seal_stage12_action_private_payload,
)
from app.services.stage12_action_runtime import (
    InMemoryStage12ActionRuntimeRepository,
    create_action_slot,
    create_objective_run,
)


def _fixture() -> SimpleNamespace:
    platform = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="stage12-owner", role="owner")
    workspace = create_workspace(
        platform, name="Stage12", owner_user_id=actor.actor_id, actor=actor
    )
    base = create_base(platform, workspace.id, name="Tasks", actor=actor)
    table = create_table(platform, base.id, name="Tasks", key="tasks", actor=actor)
    field = create_field(
        platform,
        table.id,
        name="Status",
        key="status",
        field_type="status",
        actor=actor,
    )
    title = create_field(
        platform,
        table.id,
        name="Title",
        key="title",
        field_type="text",
        actor=actor,
    )
    priority = create_field(
        platform,
        table.id,
        name="Priority",
        key="priority",
        field_type="single_select",
        options={"choices": ["high", "medium", "low"], "default": "medium"},
        actor=actor,
    )
    source_work_item = create_field(
        platform,
        table.id,
        name="Source work item",
        key="source_work_item",
        field_type="linked_record",
        actor=actor,
    )
    project_link = create_field(
        platform,
        table.id,
        name="Project",
        key="project_link",
        field_type="linked_record",
        actor=actor,
    )
    employee = create_digital_employee(
        platform,
        base.id,
        name="Action Employee",
        description="Stage12 API test",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[],
        field_policy=build_stage12_field_policy_v2(
            readable_field_ids=(
                field.id,
                title.id,
                priority.id,
                source_work_item.id,
                project_link.id,
            ),
            writable_field_ids=(
                field.id,
                title.id,
                priority.id,
                source_work_item.id,
                project_link.id,
            ),
        ),
        allowed_actions=["draft_create"],
        actor=actor,
    )
    snapshot = build_authorized_schema_snapshot(
        platform,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        require_field_policy_v2=True,
    )
    scope_hash = build_stage12_action_scope_hash(
        schema_scope_hash=snapshot.scope_hash,
        target_record_id=None,
    )
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    action_runtime = InMemoryStage12ActionRuntimeRepository()
    now = datetime.now(UTC)
    run = AgentWorkflowRun(
        id=uuid4(),
        workspace_id=workspace.id,
        root_employee_id=employee.id,
        target_record_id=None,
        parent_run_id=None,
        workflow_version="stage12.quality-v2.action.v1",
        status="waiting_approval",
        scope_hash=scope_hash,
        data_version_hash=None,
        deadline_at=now + timedelta(minutes=5),
        lease_owner=None,
        lease_expires_at=None,
        idempotency_key_hash="a" * 64,
        safe_result_ref=None,
        version=1,
    )
    runtime.add_run(run)
    objective = create_objective_run(
        action_runtime,
        run_id=run.id,
        objective_key="obj-01",
        kind="task_creation",
        required=True,
        dependency_keys=(),
    )
    command_id = uuid4()
    objective.command_id = command_id
    private_id = uuid4()
    control = ActionSlotControlV1(
        action_kind="task.create",
        confirmation_policy="required",
        dependency_keys=(),
        evidence_refs=("ev-01",),
        editable_fields=(
            {
                "field_id": field.id,
                "field_key": "status",
                "label": "状态",
                "field_type": "status",
                "required": True,
            },
        ),
        safe_summary="创建一条待确认任务",
    )
    slot = create_action_slot(
        action_runtime,
        run_id=run.id,
        objective_run_id=objective.id,
        slot_key="act-01",
        action_kind="task.create",
        control=control,
        private_payload_ref=f"agent-private-input:{private_id}",
        target_scope_hash=scope_hash,
        data_version_hash=None,
        idempotency_key_hash="b" * 64,
    )
    payload = ActionPrivatePayloadV1(
        actor_user_id=actor.actor_id,
        objective_key=objective.objective_key,
        slot_key=slot.slot_key,
        action_kind="task.create",
        field_policy_version=snapshot.field_policy_version,
        field_policy_hash=snapshot.field_policy_hash,
        candidate_set_hash="c" * 64,
        target_table_id=table.id,
        target_record_ids=(),
        assignments=({"record_id": None, "field_id": field.id, "value": "open"},),
        record_versions=(),
        evidence_ids=("ev-01",),
        expires_at=now + timedelta(minutes=5),
    )
    key = base64.urlsafe_b64encode(b"p" * 32).decode("ascii")
    sealed = seal_stage12_action_private_payload(
        payload,
        key_b64=key,
        key_version="test-v1",
        run_id=run.id,
        command_id=command_id,
        scope_hash=scope_hash,
    )
    runtime.add_private_input(
        AgentPrivateInput(
            id=private_id,
            run_id=run.id,
            command_id=command_id,
            ciphertext=sealed.ciphertext,
            nonce=sealed.nonce,
            key_version=sealed.key_version,
            aad_hash=sealed.aad_hash,
            scope_hash=sealed.scope_hash,
            expires_at=sealed.expires_at,
            consumed_at=None,
        )
    )
    materialize_action_slot(
        action_runtime,
        platform,
        slot_id=slot.id,
        expected_proposal_version=1,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        private_payload=payload,
    )
    return SimpleNamespace(
        platform=platform,
        runtime=runtime,
        action_runtime=action_runtime,
        actor=actor,
        workspace=workspace,
        employee=employee,
        table=table,
        field=field,
        run=run,
        objective=objective,
        slot=slot,
        key=key,
    )


def _client(fixture):
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: fixture.platform
    app.dependency_overrides[get_agent_event_runtime_uow] = lambda: fixture.runtime
    app.dependency_overrides[get_stage12_action_repository] = (
        lambda: fixture.action_runtime
    )
    app.dependency_overrides[get_settings] = lambda: replace(
        Settings(),
        agent_event_runtime_enabled=True,
        agent_event_runtime_allowed_workspace_ids=(str(fixture.workspace.id),),
        agent_runtime_input_key=fixture.key,
        durable_action_v1_mode="isolated",
        durable_action_v1_workspace_allowlist=(str(fixture.workspace.id),),
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["X-Stage06-User-Id"] = fixture.actor.actor_id
    return client


def test_objective_action_read_and_confirm_are_safe_and_idempotent() -> None:
    fixture = _fixture()
    with _client(fixture) as client:
        objectives = client.get(f"/api/stage10/agent-runs/{fixture.run.id}/objectives")
        actions = client.get(f"/api/stage10/agent-runs/{fixture.run.id}/actions")
        confirmed = client.post(
            f"/api/stage10/agent-runs/{fixture.run.id}/actions/{fixture.slot.id}/confirm",
            headers={"Idempotency-Key": "stage12-confirm-1"},
            json={
                "proposal_version": fixture.slot.proposal_version,
                "record_version": None,
                "proposed_values": {"status": "done"},
            },
        )
        replayed = client.post(
            f"/api/stage10/agent-runs/{fixture.run.id}/actions/{fixture.slot.id}/confirm",
            headers={"Idempotency-Key": "stage12-confirm-1"},
            json={
                "proposal_version": 4,
                "record_version": None,
                "proposed_values": {"status": "done"},
            },
        )

    assert objectives.status_code == 200, objectives.text
    assert objectives.json()["objectives"][0]["objective_key"] == "obj-01"
    assert actions.status_code == 200, actions.text
    assert actions.json()["actions"][0]["proposed_values"] == {"status": "open"}
    assert "agent-private-input" not in actions.text
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "executed"
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["replayed"] is True
    assert len(fixture.platform.records) == 1
    assert fixture.platform.records[0].values == {"status": "done"}


def test_action_confirm_rejects_unknown_fields_and_scope_drift() -> None:
    fixture = _fixture()
    with _client(fixture) as client:
        invalid = client.post(
            f"/api/stage10/agent-runs/{fixture.run.id}/actions/{fixture.slot.id}/confirm",
            headers={"Idempotency-Key": "stage12-confirm-invalid"},
            json={
                "proposal_version": fixture.slot.proposal_version,
                "record_version": None,
                "proposed_values": {"hidden": "leak"},
            },
        )
        fixture.run.scope_hash = "f" * 64
        denied = client.get(f"/api/stage10/agent-runs/{fixture.run.id}/actions")

    assert invalid.status_code == 403, invalid.text
    assert invalid.json()["detail"]["code"] == "action_scope_changed"
    assert fixture.platform.records == []
    assert denied.status_code == 403, denied.text


def test_action_read_and_confirm_fail_closed_after_employee_scope_is_revoked() -> None:
    fixture = _fixture()
    fixture.employee.allowed_actions = []
    fixture.employee.accessible_tables = []

    with _client(fixture) as client:
        actions = client.get(f"/api/stage10/agent-runs/{fixture.run.id}/actions")
        confirmed = client.post(
            f"/api/stage10/agent-runs/{fixture.run.id}/actions/"
            f"{fixture.slot.id}/confirm",
            headers={"Idempotency-Key": "stage12-confirm-revoked-scope"},
            json={
                "proposal_version": fixture.slot.proposal_version,
                "record_version": None,
                "proposed_values": {"status": "done"},
            },
        )

    assert actions.status_code == 403, actions.text
    assert actions.json()["detail"]["code"] == "action_scope_changed"
    assert confirmed.status_code == 403, confirmed.text
    assert confirmed.json()["detail"]["code"] == "action_scope_changed"
    assert fixture.platform.records == []


def test_action_read_fails_closed_after_field_permission_is_revoked() -> None:
    fixture = _fixture()
    fixture.field.permission_policy = {"owner": "hidden"}

    with _client(fixture) as client:
        actions = client.get(f"/api/stage10/agent-runs/{fixture.run.id}/actions")

    assert actions.status_code == 403, actions.text
    assert actions.json()["detail"]["code"] == "action_scope_changed"
    assert fixture.platform.records == []


def test_action_read_and_confirm_fail_closed_after_employee_field_policy_contracts() -> None:
    fixture = _fixture()
    fixture.employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=(),
        writable_field_ids=(),
    )

    with _client(fixture) as client:
        actions = client.get(f"/api/stage10/agent-runs/{fixture.run.id}/actions")
        confirmed = client.post(
            f"/api/stage10/agent-runs/{fixture.run.id}/actions/"
            f"{fixture.slot.id}/confirm",
            headers={"Idempotency-Key": "stage12-confirm-policy-contracted"},
            json={
                "proposal_version": fixture.slot.proposal_version,
                "record_version": None,
                "proposed_values": {"status": "done"},
            },
        )

    assert actions.status_code == 403, actions.text
    assert actions.json()["detail"]["code"] == "action_scope_changed"
    assert confirmed.status_code == 403, confirmed.text
    assert confirmed.json()["detail"]["code"] == "action_scope_changed"
    assert fixture.platform.records == []


def test_action_confirmation_is_disabled_by_independent_kill_switch() -> None:
    fixture = _fixture()
    app = create_app()
    app.dependency_overrides[get_stage06_platform_uow] = lambda: fixture.platform
    app.dependency_overrides[get_agent_event_runtime_uow] = lambda: fixture.runtime
    app.dependency_overrides[get_stage12_action_repository] = (
        lambda: fixture.action_runtime
    )
    app.dependency_overrides[get_settings] = lambda: replace(
        Settings(),
        agent_event_runtime_enabled=True,
        agent_event_runtime_allowed_workspace_ids=(str(fixture.workspace.id),),
        agent_runtime_input_key=fixture.key,
        durable_action_v1_mode="off",
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["X-Stage06-User-Id"] = fixture.actor.actor_id

    with client:
        actions = client.get(f"/api/stage10/agent-runs/{fixture.run.id}/actions")
        confirmed = client.post(
            f"/api/stage10/agent-runs/{fixture.run.id}/actions/"
            f"{fixture.slot.id}/confirm",
            headers={"Idempotency-Key": "stage12-confirm-runtime-off"},
            json={
                "proposal_version": fixture.slot.proposal_version,
                "record_version": None,
                "proposed_values": {"status": "done"},
            },
        )

    assert actions.status_code == 200, actions.text
    assert confirmed.status_code == 409, confirmed.text
    assert confirmed.json()["detail"]["code"] == "durable_action_runtime_disabled"
    assert fixture.platform.records == []


def test_action_admission_defaults_to_unchanged_v1_path(monkeypatch) -> None:
    fixture = _fixture()
    settings = replace(
        Settings(),
        agent_event_runtime_enabled=True,
        agent_event_runtime_allowed_workspace_ids=(str(fixture.workspace.id),),
        agent_runtime_input_key=fixture.key,
        durable_action_v1_mode="off",
    )
    monkeypatch.setattr(agent_run_routes, "get_settings", lambda: settings)

    def fail_if_stage12_admission_runs(*_args, **_kwargs):
        raise AssertionError("stage12_action_admission_must_stay_off")

    monkeypatch.setattr(
        agent_run_routes,
        "admit_stage12_action_run",
        fail_if_stage12_admission_runs,
    )

    with _client(fixture) as client:
        response = client.post(
            "/api/stage10/agent-runs",
            json={
                "workspace_id": str(fixture.workspace.id),
                "employee_id": str(fixture.run.root_employee_id),
                "intent": "controlled_action",
                "query": "创建回滚方案评审任务",
                "requested_action": "task_create",
                "target_record_id": None,
                "idempotency_key": "stage12-api-action-off",
                "skill_id": None,
            },
        )

    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "agent_run_scope_denied"


def test_create_action_run_uses_stage12_admission_and_stops_at_confirmation(
    monkeypatch,
) -> None:
    fixture = _fixture()
    settings = replace(
        Settings(),
        agent_event_runtime_enabled=True,
        agent_event_runtime_allowed_workspace_ids=(str(fixture.workspace.id),),
        agent_runtime_input_key=fixture.key,
        durable_action_v1_mode="isolated",
        durable_action_v1_workspace_allowlist=(str(fixture.workspace.id),),
    )
    monkeypatch.setattr(agent_run_routes, "get_settings", lambda: settings)

    with _client(fixture) as client:
        response = client.post(
            "/api/stage10/agent-runs",
            json={
                "workspace_id": str(fixture.workspace.id),
                "employee_id": str(fixture.run.root_employee_id),
                "intent": "controlled_action",
                "query": "创建回滚方案评审任务",
                "requested_action": "task_create",
                "target_record_id": None,
                "idempotency_key": "stage12-api-action-create-1",
                "skill_id": None,
            },
        )
        events = client.get(
            f"/api/stage10/agent-runs/{response.json()['run_id']}/events"
        )

    assert response.status_code == 202, response.text
    assert response.json()["status"] == "waiting_approval"
    assert events.status_code == 200, events.text
    assert "event: objective" in events.text
    assert "objective.started" in events.text
    assert "event: action" in events.text
    assert "action.pending_confirmation" in events.text
    assert len(fixture.platform.record_change_drafts) == 2
    assert fixture.platform.records == []


def test_public_auto_action_admission_discovers_multiple_slots_without_hints(
    monkeypatch,
) -> None:
    fixture = _fixture()
    fixture.employee.allowed_actions = ["draft_create", "notification.request"]
    settings = replace(
        Settings(),
        agent_event_runtime_enabled=True,
        agent_event_runtime_allowed_workspace_ids=(str(fixture.workspace.id),),
        agent_runtime_input_key=fixture.key,
        durable_action_v1_mode="isolated",
        durable_action_v1_workspace_allowlist=(str(fixture.workspace.id),),
    )
    monkeypatch.setattr(agent_run_routes, "get_settings", lambda: settings)

    with _client(fixture) as client:
        response = client.post(
            "/api/stage10/agent-runs",
            json={
                "workspace_id": str(fixture.workspace.id),
                "employee_id": str(fixture.employee.id),
                "intent": "controlled_action",
                "query": "创建复盘任务，并提醒负责人反馈，不要直接发送",
                "requested_action": "auto",
                "target_record_id": None,
                "idempotency_key": "stage12-api-action-auto-1",
                "skill_id": None,
            },
        )
        assert response.status_code == 202, response.text
        actions = client.get(
            f"/api/stage10/agent-runs/{response.json()['run_id']}/actions"
        )

    assert actions.status_code == 200, actions.text
    assert {item["action_kind"] for item in actions.json()["actions"]} == {
        "task.create",
        "reminder.request",
    }
    assert fixture.platform.records == []
    assert fixture.platform.notification_requests == []
