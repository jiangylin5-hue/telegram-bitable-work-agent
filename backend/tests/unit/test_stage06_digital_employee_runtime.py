from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    bind_telegram_context,
    confirm_record_change_draft,
    create_digital_employee,
    create_notification_request,
    invoke_digital_employee,
    list_record_change_drafts,
    resolve_telegram_mention,
)
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_form_view,
    create_record,
    create_table,
    create_workspace,
)


def test_stage06_digital_employee_summarizes_permission_filtered_view_and_writes_agent_run() -> None:
    uow, view, _record = _workspace_with_customer_view()
    employee = create_digital_employee(
        uow,
        view.base_id,
        name="CRM Helper",
        description="Summarize customer view",
        telegram_alias="crm",
        accessible_tables=[],
        accessible_views=[str(view.id)],
        allowed_actions=["query", "summarize", "draft_update"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )

    response = invoke_digital_employee(
        uow,
        employee.id,
        action="summarize",
        view_id=view.id,
        actor=Actor(actor_type="user", actor_id="viewer-1", role="viewer"),
    )

    assert response["action"] == "summarize"
    assert response["record_count"] == 1
    assert response["records"] == [{"name": "Ada Co", "status": "new"}]
    assert "private" not in str(response)
    skill_evidence = response["skill_evidence"]
    selected_ids = {item["skill_id"] for item in skill_evidence["selected_skills"]}
    assert "platform-base" in selected_ids
    assert "platform-tabular-analysis" in selected_ids
    assert "platform-shared-policy" in selected_ids
    assert uow.agent_runs[-1].agent_name == "CRM Helper"
    assert uow.agent_runs[-1].status == "succeeded"
    assert uow.agent_runs[-1].output_summary["skill_evidence"][
        "manifest_version"
    ] == "stage06-larksuite-skills-v1"
    assert uow.audit_events[-1].event_type == "stage06.digital_employee_invoked"


def test_stage06_digital_employee_write_like_action_creates_draft_not_record_update() -> None:
    uow, view, record = _workspace_with_customer_view()
    employee = create_digital_employee(
        uow,
        view.base_id,
        name="CRM Helper",
        description="Draft updates",
        telegram_alias="crm",
        accessible_tables=[str(record.table_id)],
        accessible_views=[str(view.id)],
        allowed_actions=["draft_update"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )

    response = invoke_digital_employee(
        uow,
        employee.id,
        action="draft_update",
        view_id=view.id,
        record_id=record.id,
        proposed_values={"status": "active"},
        actor=Actor(actor_type="user", actor_id="operator-1", role="operator"),
    )

    assert response["draft_id"] == str(uow.record_change_drafts[0].id)
    assert response["status"] == "pending_confirmation"
    assert record.values["status"] == "new"
    assert uow.record_change_drafts[0].before_values == {"status": "new"}

    confirmed = confirm_record_change_draft(
        uow,
        uow.record_change_drafts[0].id,
        actor=Actor(actor_type="user", actor_id="operator-1", role="operator"),
    )

    assert confirmed.status == "confirmed"
    assert record.values["status"] == "active"
    assert record.version == 2
    assert uow.audit_events[-1].event_type == "stage06.record_change_draft_confirmed"


def test_stage06_telegram_mention_resolves_bound_employee_context() -> None:
    uow, view, _record = _workspace_with_customer_view()
    workspace = uow.workspaces[0]
    employee = create_digital_employee(
        uow,
        view.base_id,
        name="CRM Helper",
        description="Summarize customer view",
        telegram_alias="crm",
        accessible_tables=[],
        accessible_views=[str(view.id)],
        allowed_actions=["summarize"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )
    bind_telegram_context(
        uow,
        workspace.id,
        workspace_member_id=uow.workspace_members[0].id,
        telegram_chat_id="chat-1",
        telegram_user_id="user-1",
        default_base_id=view.base_id,
        default_digital_employee_id=employee.id,
        scope_policy={"views": [str(view.id)]},
    )

    response = resolve_telegram_mention(
        uow,
        telegram_chat_id="chat-1",
        telegram_user_id="user-1",
        alias="crm",
        text="summarize",
    )

    assert response["employee_id"] == str(employee.id)
    assert response["base_id"] == str(view.base_id)
    assert response["action"] == "summarize"
    assert response["record_count"] == 1


def test_stage06_notification_request_stays_controlled_and_audited() -> None:
    uow, view, record = _workspace_with_customer_view()

    request = create_notification_request(
        uow,
        workspace_id=uow.workspaces[0].id,
        base_id=view.base_id,
        source_record_id=record.id,
        channel="telegram",
        target={"telegram_chat_id": "chat-1"},
        message_payload={"text": "Review customer Ada Co"},
        send_policy={"dry_run": True, "allowlist": ["chat-2"]},
        actor=Actor(actor_type="user", actor_id="operator-1", role="operator"),
    )

    assert request.status == "blocked"
    assert uow.notification_requests == [request]
    assert uow.audit_events[-1].event_type == "stage06.notification_blocked"


def test_stage06_record_change_drafts_can_be_listed_by_base() -> None:
    uow, view, record = _workspace_with_customer_view()
    employee = create_digital_employee(
        uow,
        view.base_id,
        name="CRM Helper",
        description="Draft updates",
        telegram_alias="crm",
        accessible_tables=[str(record.table_id)],
        accessible_views=[str(view.id)],
        allowed_actions=["draft_update"],
        actor=Actor(actor_type="user", actor_id="owner-1", role="owner"),
    )
    invoke_digital_employee(
        uow,
        employee.id,
        action="draft_update",
        view_id=view.id,
        record_id=record.id,
        proposed_values={"status": "active"},
        actor=Actor(actor_type="user", actor_id="operator-1", role="operator"),
    )

    drafts = list_record_change_drafts(uow, view.base_id)

    assert [draft.id for draft in drafts] == [uow.record_change_drafts[0].id]


def _workspace_with_customer_view():
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Acme", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Name", key="name", field_type="text")
    create_field(
        uow,
        table.id,
        name="Status",
        key="status",
        field_type="status",
        permission_policy={"viewer": "read", "operator": "write"},
    )
    create_field(
        uow,
        table.id,
        name="Internal Notes",
        key="internal_notes",
        field_type="text",
        permission_policy={"viewer": "hidden", "operator": "write"},
    )
    record = create_record(
        uow,
        table.id,
        values={"name": "Ada Co", "status": "new", "internal_notes": "private"},
    )
    view = create_form_view(
        uow,
        base.id,
        table.id,
        name="Customer Grid",
        view_type="grid",
        config={"fields": ["name", "status", "internal_notes"]},
    )
    return uow, view, record
