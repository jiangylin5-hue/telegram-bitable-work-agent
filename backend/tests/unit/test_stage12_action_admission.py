from datetime import UTC, datetime
import base64

import pytest

from app.schemas.agent_event_runtime import AgentRunCreateRequest
from app.services.agent_event_runtime import InMemoryAgentEventRuntimeUnitOfWork
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
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
from app.services.stage12_action_admission import admit_stage12_action_run
from app.services.stage12_action_private_payload import (
    open_stage12_action_private_payload,
)
from app.services.stage12_action_runtime import InMemoryStage12ActionRuntimeRepository
from scripts.stage12_evaluation_fixture import materialize_stage12_evaluation_fixture


def test_task_create_admission_runs_planner_persists_and_materializes_pending() -> None:
    platform = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(
        platform, name="Stage12", owner_user_id=actor.actor_id, actor=actor
    )
    base = create_base(platform, workspace.id, name="Tasks", actor=actor)
    table = create_table(platform, base.id, name="Tasks", key="tasks", actor=actor)
    title = create_field(
        platform,
        table.id,
        name="Title",
        key="title",
        field_type="text",
        actor=actor,
    )
    status = create_field(
        platform,
        table.id,
        name="Status",
        key="status",
        field_type="status",
        options={"choices": ["planned", "done"], "default": "planned"},
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
    due_date = create_field(
        platform,
        table.id,
        name="Due date",
        key="due_date",
        field_type="date",
        actor=actor,
    )
    employee = create_digital_employee(
        platform,
        base.id,
        name="Action Employee",
        description="Stage12 admission",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[],
        allowed_actions=["draft_create"],
        actor=actor,
    )
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    actions = InMemoryStage12ActionRuntimeRepository()
    key = base64.urlsafe_b64encode(b"z" * 32).decode("ascii")

    request = AgentRunCreateRequest(
        workspace_id=workspace.id,
        employee_id=employee.id,
        intent="controlled_action",
        query="创建回滚方案评审任务",
        requested_action="task_create",
        target_record_id=None,
        idempotency_key="stage12-admission-task-1",
        skill_id=None,
    )
    with pytest.raises(
        PlatformValidationError,
        match="digital_employee_field_policy_v2_required",
    ):
        admit_stage12_action_run(
            platform,
            runtime,
            actions,
            request=request,
            actor=actor,
            private_key_b64=key,
            private_key_version="test-v1",
            embedded=True,
            now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        )

    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=(
            title.id,
            status.id,
            priority.id,
            source_work_item.id,
            project_link.id,
            due_date.id,
        ),
        writable_field_ids=(
            title.id,
            status.id,
            priority.id,
            source_work_item.id,
            project_link.id,
            due_date.id,
        ),
    )

    result = admit_stage12_action_run(
        platform,
        runtime,
        actions,
        request=request,
        actor=actor,
        private_key_b64=key,
        private_key_version="test-v1",
        embedded=True,
        now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
    )

    assert result.status == "waiting_approval"
    assert result.action_count == 1
    assert len(platform.record_change_drafts) == 1
    assert platform.record_change_drafts[0].status == "pending_confirmation"
    assert platform.records == []
    assert len(runtime.private_inputs) == 1
    assert "回滚方案".encode("utf-8") not in runtime.private_inputs[0].ciphertext
    assert [item.event_type for item in runtime.events][
        -1
    ] == "action.pending_confirmation"

    employee.allowed_actions = ["draft_create", "notification.request"]
    blind = admit_stage12_action_run(
        platform,
        runtime,
        actions,
        request=AgentRunCreateRequest(
            workspace_id=workspace.id,
            employee_id=employee.id,
            intent="controlled_action",
            query="创建复盘任务，并提醒负责人今天反馈，不要直接发送",
            requested_action="auto",
            target_record_id=None,
            idempotency_key="stage12-admission-auto-1",
            skill_id=None,
        ),
        actor=actor,
        private_key_b64=key,
        private_key_version="test-v1",
        embedded=True,
        now=datetime(2026, 7, 30, 9, 5, tzinfo=UTC),
    )

    assert blind.action_count == 2
    assert {item.action_kind for item in actions.list_actions(blind.run_id)} == {
        "task.create",
        "reminder.request",
    }


def test_blind_update_resolves_planner_record_code_without_api_target_hint() -> None:
    platform = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    fixture = materialize_stage12_evaluation_fixture(platform, actor)
    employee = create_digital_employee(
        platform,
        fixture.base_id,
        name="Blind Action Employee",
        description="Stage12 blind target admission",
        telegram_alias=None,
        accessible_tables=[str(value) for value in fixture.table_ids.values()],
        accessible_views=[],
        allowed_actions=["draft_update"],
        actor=actor,
    )
    field_ids = tuple(
        field.id
        for table_id in fixture.table_ids.values()
        for field in platform.list_fields(table_id)
    )
    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=field_ids,
        writable_field_ids=field_ids,
    )
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    actions = InMemoryStage12ActionRuntimeRepository()
    initial_record_count = len(platform.records)

    result = admit_stage12_action_run(
        platform,
        runtime,
        actions,
        request=AgentRunCreateRequest(
            workspace_id=fixture.core.workspace_id,
            employee_id=employee.id,
            intent="controlled_action",
            query="把 MT-014 的 status 提议改为 in_progress，等待我确认。",
            requested_action="auto",
            target_record_id=None,
            idempotency_key="stage12-blind-update-mt-014",
            skill_id=None,
        ),
        actor=actor,
        private_key_b64=base64.urlsafe_b64encode(b"z" * 32).decode("ascii"),
        private_key_version="test-v1",
        embedded=True,
        now=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
    )

    assert result.status == "waiting_approval"
    assert result.action_count == 1
    action = actions.list_actions(result.run_id)[0]
    assert action.action_kind == "record.update"
    assert action.status == "pending_confirmation"
    assert len(platform.records) == initial_record_count
    assert platform.record_change_drafts[-1].status == "pending_confirmation"


def test_task_create_resolves_project_owner_selector_to_authorized_record_id() -> None:
    platform = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    fixture = materialize_stage12_evaluation_fixture(platform, actor)
    employee = create_digital_employee(
        platform,
        fixture.base_id,
        name="Owner assignment employee",
        description="Stage12 project owner binding",
        telegram_alias=None,
        accessible_tables=[str(value) for value in fixture.table_ids.values()],
        accessible_views=[],
        allowed_actions=["draft_create"],
        actor=actor,
    )
    field_ids = tuple(
        field.id
        for table_id in fixture.table_ids.values()
        for field in platform.list_fields(table_id)
    )
    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=field_ids,
        writable_field_ids=field_ids,
    )
    runtime = InMemoryAgentEventRuntimeUnitOfWork()
    actions = InMemoryStage12ActionRuntimeRepository()
    key = base64.urlsafe_b64encode(b"z" * 32).decode("ascii")
    now = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)

    result = admit_stage12_action_run(
        platform,
        runtime,
        actions,
        request=AgentRunCreateRequest(
            workspace_id=fixture.core.workspace_id,
            employee_id=employee.id,
            intent="controlled_action",
            query="为 PRJ-ATLAS 创建高优先级范围确认任务并指派项目负责人，等待确认。",
            requested_action="task_create",
            target_record_id=None,
            idempotency_key="stage12-project-owner-binding",
            skill_id=None,
        ),
        actor=actor,
        private_key_b64=key,
        private_key_version="test-v1",
        embedded=True,
        now=now,
    )

    private_input = runtime.private_inputs[0]
    payload = open_stage12_action_private_payload(
        private_input,
        key_b64=key,
        run_id=result.run_id,
        command_id=private_input.command_id,
        scope_hash=private_input.scope_hash,
        now=now,
    )
    assignee_field = next(
        field
        for field in platform.list_fields(fixture.table_ids["tasks"])
        if field.key == "assignee"
    )
    owner_record = next(
        record
        for record in platform.list_records(fixture.table_ids["owners"])
        if record.values.get("owner_code") == "OWNER-ATLAS"
    )
    project_field = next(
        field
        for field in platform.list_fields(fixture.table_ids["tasks"])
        if field.key == "project_link"
    )
    project_record = next(
        record
        for record in platform.list_records(fixture.table_ids["projects"])
        if record.values.get("project_code") == "PRJ-ATLAS"
    )
    assignee = next(
        assignment
        for assignment in payload.assignments
        if assignment.field_id == assignee_field.id
    )

    assert assignee.value == [str(owner_record.id)]
    project_link = next(
        assignment
        for assignment in payload.assignments
        if assignment.field_id == project_field.id
    )
    assert project_link.value == [str(project_record.id)]
    assert platform.record_change_drafts[-1].proposed_values["assignee"] == [
        str(owner_record.id)
    ]
    assert platform.record_change_drafts[-1].proposed_values["project_link"] == [
        str(project_record.id)
    ]
