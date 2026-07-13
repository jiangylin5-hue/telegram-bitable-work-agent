from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.adapters.llm_openrouter import OpenRouterStructuredLLMClient
from app.agents.interfaces import StructuredLLMClient, StructuredLLMResult
from app.agents.stage06_live_digital_employee import run_stage06_live_employee
from app.agents.stage06_skill_matching import build_stage06_skill_evidence
from app.models.agent import AgentRun
from app.models.stage06_platform import Stage06TelegramBinding
from app.models.stage06_runtime import (
    DigitalEmployee,
    NotificationRequest,
    RecordChangeDraft,
)
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_audit import sanitize_stage06_audit_state
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    get_table_schema,
    list_view_records,
    read_base,
    update_record,
)


class Stage06RuntimeUnitOfWork(Stage06PlatformUnitOfWork, Protocol):
    pass


READ_ACTIONS = frozenset({"schema_inspect", "query", "summarize"})
WRITE_LIKE_ACTIONS = frozenset({"draft_create", "draft_update", "status_advance"})


def create_digital_employee(
    uow: Stage06RuntimeUnitOfWork,
    base_id: UUID,
    *,
    name: str,
    description: str,
    telegram_alias: str | None,
    accessible_tables: list[str],
    accessible_views: list[str],
    allowed_actions: list[str],
    actor: Actor,
    field_policy: dict[str, Any] | None = None,
    confirmation_policy: dict[str, Any] | None = None,
    response_style: dict[str, Any] | None = None,
) -> DigitalEmployee:
    base = read_base(uow, base_id)
    _validate_employee_scope(
        uow,
        base_id=base.id,
        accessible_tables=accessible_tables,
        accessible_views=accessible_views,
    )
    employee = DigitalEmployee(
        id=uuid4(),
        workspace_id=base.workspace_id,
        base_id=base.id,
        name=name,
        description=description,
        telegram_alias=telegram_alias,
        accessible_tables=list(accessible_tables),
        accessible_views=list(accessible_views),
        field_policy=field_policy or {},
        allowed_actions=list(allowed_actions),
        confirmation_policy=confirmation_policy
        or {"draft_create": "required", "draft_update": "required"},
        response_style=response_style or {},
        status="active",
        version=1,
        access_mode="workspace",
    )
    uow.add_digital_employee(employee)
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type="stage06.digital_employee_created",
        entity_type="digital_employee",
        entity_id=employee.id,
        after_state={
            "base_id": str(base_id),
            "telegram_alias": telegram_alias,
            "allowed_actions": allowed_actions,
        },
    )
    return employee


def update_digital_employee(
    uow: Stage06RuntimeUnitOfWork,
    employee_id: UUID,
    *,
    actor: Actor,
    name: str | None = None,
    description: str | None = None,
    telegram_alias: str | None = None,
    accessible_tables: list[str] | None = None,
    accessible_views: list[str] | None = None,
    allowed_actions: list[str] | None = None,
    field_policy: dict[str, Any] | None = None,
    confirmation_policy: dict[str, Any] | None = None,
    response_style: dict[str, Any] | None = None,
    status: str | None = None,
) -> DigitalEmployee:
    employee = _require_employee_for_update(uow, employee_id)
    before_state = {
        "name": employee.name,
        "description": employee.description,
        "telegram_alias": employee.telegram_alias,
        "allowed_actions": list(employee.allowed_actions),
        "status": employee.status,
    }
    if name is not None:
        employee.name = name
    if description is not None:
        employee.description = description
    if telegram_alias is not None:
        employee.telegram_alias = telegram_alias
    if accessible_tables is not None:
        _validate_employee_scope(
            uow,
            base_id=employee.base_id,
            accessible_tables=accessible_tables,
            accessible_views=(
                accessible_views
                if accessible_views is not None
                else employee.accessible_views
            ),
        )
        employee.accessible_tables = list(accessible_tables)
    if accessible_views is not None:
        _validate_employee_scope(
            uow,
            base_id=employee.base_id,
            accessible_tables=(
                accessible_tables
                if accessible_tables is not None
                else employee.accessible_tables
            ),
            accessible_views=accessible_views,
        )
        employee.accessible_views = list(accessible_views)
    if allowed_actions is not None:
        employee.allowed_actions = list(allowed_actions)
    if field_policy is not None:
        employee.field_policy = dict(field_policy)
    if confirmation_policy is not None:
        employee.confirmation_policy = dict(confirmation_policy)
    if response_style is not None:
        employee.response_style = dict(response_style)
    if status is not None:
        employee.status = status
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type="stage06.digital_employee_updated",
        entity_type="digital_employee",
        entity_id=employee.id,
        after_state={
            "before": before_state,
            "after": {
                "name": employee.name,
                "description": employee.description,
                "telegram_alias": employee.telegram_alias,
                "allowed_actions": list(employee.allowed_actions),
                "status": employee.status,
            },
        },
    )
    return employee


def invoke_digital_employee(
    uow: Stage06RuntimeUnitOfWork,
    employee_id: UUID,
    *,
    action: str,
    actor: Actor,
    view_id: UUID | None = None,
    table_id: UUID | None = None,
    record_id: UUID | None = None,
    proposed_values: dict[str, Any] | None = None,
    runtime_mode: str = "deterministic",
    prompt: str | None = None,
    llm_client: StructuredLLMClient | None = None,
    view_records_override: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    employee = _require_employee(uow, employee_id)
    _assert_employee_action(employee, action)
    if view_records_override is not None and (
        runtime_mode != "live_openrouter" or action != "summarize"
    ):
        raise PlatformValidationError(
            "live_employee_record_override_not_allowed",
            action,
        )
    skill_evidence = _build_skill_evidence_for_invocation(
        employee=employee,
        action=action,
        actor=actor,
        prompt=prompt,
        view_id=view_id,
        table_id=table_id,
        record_id=record_id,
    )
    if runtime_mode == "live_openrouter":
        response = _invoke_live_digital_employee(
            uow,
            employee,
            action=action,
            actor=actor,
            view_id=view_id,
            record_id=record_id,
            prompt=prompt,
            llm_client=llm_client,
            skill_evidence=skill_evidence,
            view_records_override=view_records_override,
        )
        _record_runtime_audit(
            uow,
            actor=actor,
            event_type="stage06.digital_employee_invoked",
            entity_type="digital_employee",
            entity_id=employee.id,
            after_state={"action": action, "output": _safe_output_summary(response)},
        )
        return response
    if runtime_mode != "deterministic":
        raise PlatformValidationError("unsupported_employee_runtime_mode", runtime_mode)
    if action == "schema_inspect":
        if table_id is None:
            raise PlatformValidationError("table_required", action)
        _assert_table_in_scope(employee, table_id)
        response = {
            "action": action,
            "schema": get_table_schema(uow, table_id),
            "skill_evidence": skill_evidence,
        }
    elif action in {"query", "summarize"}:
        if view_id is None:
            raise PlatformValidationError("view_required", action)
        _assert_view_in_scope(employee, view_id)
        view_records = list_view_records(uow, view_id, actor=actor)
        records = [record["fields"] for record in view_records["records"]]
        response = {
            "action": action,
            "employee_id": str(employee.id),
            "view_id": str(view_id),
            "record_count": len(records),
            "records": records,
            "skill_evidence": skill_evidence,
        }
    elif action in {"draft_update", "status_advance"}:
        if record_id is None or proposed_values is None:
            raise PlatformValidationError("draft_update_payload_required", action)
        response = _create_update_draft_response(
            uow,
            employee,
            record_id=record_id,
            proposed_values=proposed_values,
            actor=actor,
        )
        response["skill_evidence"] = skill_evidence
    else:
        raise PlatformValidationError("unsupported_employee_action", action)

    _record_agent_run(uow, employee=employee, action=action, actor=actor, output=response)
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type="stage06.digital_employee_invoked",
        entity_type="digital_employee",
        entity_id=employee.id,
        after_state={"action": action, "output": _safe_output_summary(response)},
    )
    return response


def _invoke_live_digital_employee(
    uow: Stage06RuntimeUnitOfWork,
    employee: DigitalEmployee,
    *,
    action: str,
    actor: Actor,
    view_id: UUID | None,
    record_id: UUID | None,
    prompt: str | None,
    llm_client: StructuredLLMClient | None,
    skill_evidence: dict[str, object],
    view_records_override: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if action not in {"summarize", "draft_update"}:
        raise PlatformValidationError("unsupported_live_employee_action", action)
    if view_id is None:
        raise PlatformValidationError("view_required", action)
    _assert_view_in_scope(employee, view_id)
    if view_records_override is None:
        view_payload = list_view_records(uow, view_id, actor=actor)
        visible_records = [
            {"id": record["id"], "fields": record["fields"]}
            for record in view_payload["records"]
        ]
    else:
        visible_records = _normalize_live_view_records_override(view_records_override)
    visible_field_keys = _visible_field_keys(visible_records)
    schema = {
        "view_id": str(view_id),
        "visible_field_keys": visible_field_keys,
    }
    if action == "draft_update":
        if record_id is None:
            raise PlatformValidationError("record_required", action)
        record = uow.get_record(record_id)
        if record is None:
            raise PlatformValidationError("record_not_found", str(record_id))
        _assert_table_in_scope(employee, record.table_id)

    client = llm_client or OpenRouterStructuredLLMClient()
    try:
        result = run_stage06_live_employee(
            action=action,
            employee_name=employee.name,
            prompt=prompt,
            schema=schema,
            records=visible_records,
            record_id=None if record_id is None else str(record_id),
            llm_client=client,
            skill_evidence=skill_evidence,
        )
    except RuntimeError as exc:
        raise PlatformValidationError("openrouter_runtime_error", str(exc)) from exc
    except ValueError as exc:
        raise PlatformValidationError("live_employee_invalid_output", str(exc)) from exc

    content = result.content
    response: dict[str, Any] = {
        "action": action,
        "employee_id": str(employee.id),
        "view_id": str(view_id),
        "record_count": len(visible_records),
        "records": [record["fields"] for record in visible_records],
        "answer": str(content["answer"]),
        "citations": content.get("citations", []),
        "runtime": {
            "mode": "live_openrouter",
            "graph_name": "stage06_live_digital_employee",
            "model_provider": result.model_provider,
            "model_name": result.model_name,
        },
        "skill_evidence": skill_evidence,
    }
    if action == "draft_update":
        draft_payload = content["draft"]
        draft_response = _create_update_draft_response(
            uow,
            employee,
            record_id=UUID(str(draft_payload["record_id"])),
            proposed_values=dict(draft_payload["proposed_values"]),
            actor=actor,
        )
        response.update(
            {
                "draft_id": draft_response["draft_id"],
                "status": draft_response["status"],
                "record_id": draft_response["record_id"],
            }
        )
    _record_live_agent_run(
        uow,
        employee=employee,
        action=action,
        actor=actor,
        output=response,
        result=result,
        record_count=len(visible_records),
    )
    return response


def _normalize_live_view_records_override(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for record in records:
        record_id = record.get("id")
        fields = record.get("fields")
        if not isinstance(record_id, str) or not record_id:
            raise PlatformValidationError("live_employee_override_invalid", "record_id")
        if not isinstance(fields, dict):
            raise PlatformValidationError("live_employee_override_invalid", "fields")
        normalized.append({"id": record_id, "fields": dict(fields)})
    return normalized


def _build_skill_evidence_for_invocation(
    *,
    employee: DigitalEmployee,
    action: str,
    actor: Actor,
    prompt: str | None,
    view_id: UUID | None,
    table_id: UUID | None = None,
    record_id: UUID | None = None,
) -> dict[str, object]:
    source_context: dict[str, object] = {
        "actor_user_id": actor.actor_id,
        "digital_employee_id": str(employee.id),
        "base_id": str(employee.base_id),
    }
    if view_id is not None:
        source_context["view_id"] = str(view_id)
    if table_id is not None:
        source_context["table_id"] = str(table_id)
    if record_id is not None:
        source_context["record_id"] = str(record_id)
    if employee.telegram_alias:
        source_context["alias"] = employee.telegram_alias
    return build_stage06_skill_evidence(
        action=action,
        source_text=prompt or action,
        source_context=source_context,
    )


def list_record_change_drafts(
    uow: Stage06RuntimeUnitOfWork,
    base_id: UUID,
) -> list[RecordChangeDraft]:
    return uow.list_record_change_drafts(base_id)


def confirm_record_change_draft(
    uow: Stage06RuntimeUnitOfWork,
    draft_id: UUID,
    *,
    actor: Actor,
) -> RecordChangeDraft:
    draft = _require_draft(uow, draft_id)
    if draft.status != "pending_confirmation":
        raise PlatformValidationError("record_change_draft_invalid_state", str(draft_id))
    if draft.record_id is None:
        raise PlatformValidationError("record_change_draft_missing_record", str(draft_id))
    update_record(
        uow,
        draft.record_id,
        values=draft.proposed_values,
        expected_version=draft.expected_version,
        actor=actor,
    )
    draft.status = "confirmed"
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type="stage06.record_change_draft_confirmed",
        entity_type="record_change_draft",
        entity_id=draft.id,
        after_state={"record_id": str(draft.record_id), "status": draft.status},
    )
    return draft


def reject_record_change_draft(
    uow: Stage06RuntimeUnitOfWork,
    draft_id: UUID,
    *,
    actor: Actor,
) -> RecordChangeDraft:
    draft = _require_draft(uow, draft_id)
    if draft.status != "pending_confirmation":
        raise PlatformValidationError("record_change_draft_invalid_state", str(draft_id))
    draft.status = "rejected"
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type="stage06.record_change_draft_rejected",
        entity_type="record_change_draft",
        entity_id=draft.id,
        after_state={"status": draft.status},
    )
    return draft


def bind_telegram_context(
    uow: Stage06RuntimeUnitOfWork,
    workspace_id: UUID,
    *,
    workspace_member_id: UUID,
    telegram_chat_id: str,
    telegram_user_id: str,
    default_base_id: UUID | None,
    default_digital_employee_id: UUID | None,
    scope_policy: dict[str, Any],
    binding_type: str = "chat_user",
) -> Stage06TelegramBinding:
    workspace = uow.get_workspace(workspace_id)
    if workspace is None:
        raise PlatformValidationError("workspace_not_found", str(workspace_id))
    member = uow.get_workspace_member(workspace_member_id)
    if (
        member is None
        or member.workspace_id != workspace_id
        or member.status != "active"
    ):
        raise PlatformValidationError("resource_scope_mismatch", "telegram_member_workspace")
    if default_base_id is not None:
        base = read_base(uow, default_base_id)
        if base.workspace_id != workspace_id:
            raise PlatformValidationError("resource_scope_mismatch", "telegram_base_workspace")
    if default_digital_employee_id is not None:
        employee = _require_employee(uow, default_digital_employee_id)
        if employee.workspace_id != workspace_id:
            raise PlatformValidationError("resource_scope_mismatch", "telegram_employee_workspace")
    binding = Stage06TelegramBinding(
        id=uuid4(),
        workspace_id=workspace_id,
        workspace_member_id=workspace_member_id,
        telegram_chat_id=telegram_chat_id,
        telegram_user_id=telegram_user_id,
        binding_type=binding_type,
        default_base_id=default_base_id,
        default_digital_employee_id=default_digital_employee_id,
        scope_policy=scope_policy,
        status="active",
    )
    uow.add_telegram_binding(binding)
    return binding


def resolve_telegram_mention(
    uow: Stage06RuntimeUnitOfWork,
    *,
    telegram_chat_id: str,
    telegram_user_id: str,
    alias: str,
    text: str,
) -> dict[str, Any]:
    binding = _find_binding(uow, telegram_chat_id, telegram_user_id)
    if binding is None:
        raise PlatformValidationError("telegram_binding_not_found", telegram_chat_id)
    member = uow.get_workspace_member(binding.workspace_member_id)
    if member is None or member.status != "active":
        raise PlatformValidationError("telegram_scope_denied", alias)
    actor = Actor(
        actor_type="user",
        actor_id=member.user_id,
        role=member.role,
    )
    employee = _resolve_employee_for_binding(uow, binding, alias)
    action = _action_from_text(text)
    view_ids = _intersect_scope(employee.accessible_views, binding.scope_policy.get("views"))
    if not view_ids:
        raise PlatformValidationError("telegram_scope_denied", alias)
    response = invoke_digital_employee(
        uow,
        employee.id,
        action=action,
        view_id=UUID(view_ids[0]),
        actor=actor,
    )
    response.update(
        {
            "employee_id": str(employee.id),
            "base_id": str(employee.base_id),
            "telegram_chat_id": telegram_chat_id,
        }
    )
    return response


def create_notification_request(
    uow: Stage06RuntimeUnitOfWork,
    *,
    workspace_id: UUID,
    base_id: UUID | None,
    source_record_id: UUID | None,
    channel: str,
    target: dict[str, Any],
    message_payload: dict[str, Any],
    send_policy: dict[str, Any],
    actor: Actor,
    server_mode: str = "disabled",
    server_allowlist: tuple[str, ...] = (),
) -> NotificationRequest:
    status = _notification_status(
        target=target,
        send_policy=send_policy,
        server_mode=server_mode,
        server_allowlist=server_allowlist,
    )
    request = NotificationRequest(
        id=uuid4(),
        workspace_id=workspace_id,
        base_id=base_id,
        source_record_id=source_record_id,
        channel=channel,
        target=target,
        message_payload=message_payload,
        send_policy=send_policy,
        status=status,
        trace_id=f"stage06:notification:{uuid4()}",
    )
    uow.add_notification_request(request)
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type=(
            "stage06.notification_blocked"
            if status == "blocked"
            else "stage06.notification_requested"
        ),
        entity_type="notification_request",
        entity_id=request.id,
        after_state={"channel": channel, "status": status},
    )
    return request


def list_notification_requests(
    uow: Stage06RuntimeUnitOfWork,
    base_id: UUID,
) -> list[NotificationRequest]:
    return uow.list_notification_requests(base_id)


def confirm_notification_request(
    uow: Stage06RuntimeUnitOfWork,
    request_id: UUID,
    *,
    actor: Actor,
    server_mode: str = "disabled",
    server_allowlist: tuple[str, ...] = (),
) -> NotificationRequest:
    request = uow.get_notification_request(request_id)
    if request is None:
        raise PlatformValidationError("notification_request_not_found", str(request_id))
    if request.status != "pending_confirmation":
        raise PlatformValidationError("notification_request_invalid_state", str(request_id))
    request.status = _notification_status(
        target=request.target,
        send_policy={
            key: value
            for key, value in request.send_policy.items()
            if key != "confirmation"
        },
        server_mode=server_mode,
        server_allowlist=server_allowlist,
    )
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type="stage06.notification_confirmed",
        entity_type="notification_request",
        entity_id=request.id,
        after_state={"status": request.status, "channel": request.channel},
    )
    return request


def list_base_audit_events(
    uow: Stage06RuntimeUnitOfWork,
    base_id: UUID,
) -> list[Any]:
    related_ids = _base_related_entity_ids(uow, base_id)
    events = []
    for event in uow.list_audit_events():
        if _audit_event_matches_base(event, base_id, related_ids):
            events.append(event)
    return events


def _create_update_draft_response(
    uow: Stage06RuntimeUnitOfWork,
    employee: DigitalEmployee,
    *,
    record_id: UUID,
    proposed_values: dict[str, Any],
    actor: Actor,
) -> dict[str, Any]:
    record = uow.get_record(record_id)
    if record is None:
        raise PlatformValidationError("record_not_found", str(record_id))
    _assert_table_in_scope(employee, record.table_id)
    table = uow.get_table(record.table_id)
    if table is None:
        raise PlatformValidationError("table_not_found", str(record.table_id))
    base = read_base(uow, table.base_id)
    before_values = {
        key: record.values.get(key)
        for key in proposed_values
        if key in record.values
    }
    draft = RecordChangeDraft(
        id=uuid4(),
        workspace_id=base.workspace_id,
        base_id=base.id,
        table_id=record.table_id,
        record_id=record.id,
        draft_type="update_record",
        proposed_values=proposed_values,
        before_values=before_values,
        created_by_type="digital_employee",
        created_by_id=str(employee.id),
        status="pending_confirmation",
        confirmation_policy=employee.confirmation_policy,
        trace_id=f"stage06:draft:{uuid4()}",
        expected_version=record.version,
    )
    uow.add_record_change_draft(draft)
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type="stage06.record_change_draft_created",
        entity_type="record_change_draft",
        entity_id=draft.id,
        after_state={"record_id": str(record.id), "status": draft.status},
    )
    return {
        "action": "draft_update",
        "draft_id": str(draft.id),
        "status": draft.status,
        "record_id": str(record.id),
    }


def _record_agent_run(
    uow: Stage06RuntimeUnitOfWork,
    *,
    employee: DigitalEmployee,
    action: str,
    actor: Actor,
    output: dict[str, Any],
) -> None:
    now = datetime.now(UTC)
    uow.add_agent_run(
        AgentRun(
            id=uuid4(),
            agent_name=employee.name,
            graph_name="stage06_digital_employee_runtime",
            model_provider="local",
            model_name="deterministic_tool_gateway",
            prompt_version="stage06-runtime-v1",
            input_summary={"action": action, "actor_role": actor.role},
            output_summary=_safe_output_summary(output),
            tool_calls=[{"name": action, "status": "succeeded"}],
            status="succeeded",
            trace_id=f"stage06:agent:{employee.id}:{uuid4()}",
            started_at=now,
            completed_at=now,
            usage_summary={"llm_calls": 0},
            cost_summary={"llm_cost": 0},
            latency_ms=0,
            created_entity_refs=[],
            redaction_policy="stage06_permission_filtered",
        )
    )


def _record_live_agent_run(
    uow: Stage06RuntimeUnitOfWork,
    *,
    employee: DigitalEmployee,
    action: str,
    actor: Actor,
    output: dict[str, Any],
    result: StructuredLLMResult,
    record_count: int,
) -> None:
    now = datetime.now(UTC)
    uow.add_agent_run(
        AgentRun(
            id=uuid4(),
            agent_name=employee.name,
            graph_name="stage06_live_digital_employee",
            model_provider=result.model_provider,
            model_name=result.model_name,
            prompt_version=result.prompt_version,
            input_summary={
                "action": action,
                "actor_role": actor.role,
                "record_count": record_count,
                "runtime_mode": "live_openrouter",
            },
            output_summary=_safe_output_summary(output),
            tool_calls=[
                {"name": "list_view_records", "status": "succeeded"},
                {"name": "openrouter.chat.completions", "status": "succeeded"},
            ],
            status="succeeded",
            trace_id=f"stage06:agent:{employee.id}:{uuid4()}",
            started_at=now,
            completed_at=now,
            usage_summary=result.usage or {},
            cost_summary={"llm_cost": None},
            latency_ms=0,
            created_entity_refs=[],
            redaction_policy="stage06_permission_filtered_summary_only",
        )
    )


def _base_related_entity_ids(
    uow: Stage06RuntimeUnitOfWork,
    base_id: UUID,
) -> set[str]:
    related_ids = {str(base_id)}
    for table in uow.list_tables(base_id):
        related_ids.add(str(table.id))
        for field in uow.list_fields(table.id):
            related_ids.add(str(field.id))
        for record in uow.list_records(table.id):
            related_ids.add(str(record.id))
        for view in uow.list_views(table.id):
            related_ids.add(str(view.id))
    for employee in uow.list_digital_employees(base_id):
        related_ids.add(str(employee.id))
    for draft in uow.list_record_change_drafts(base_id):
        related_ids.add(str(draft.id))
        if draft.record_id is not None:
            related_ids.add(str(draft.record_id))
    for request in uow.list_notification_requests(base_id):
        related_ids.add(str(request.id))
        if request.source_record_id is not None:
            related_ids.add(str(request.source_record_id))
    return related_ids


def _audit_event_matches_base(
    event: Any,
    base_id: UUID,
    related_ids: set[str],
) -> bool:
    if event.entity_id is not None and str(event.entity_id) in related_ids:
        return True
    for state in (event.before_state, event.after_state, event.permission_snapshot):
        if _state_contains_base_reference(state, base_id, related_ids):
            return True
    return False


def _state_contains_base_reference(
    state: Any,
    base_id: UUID,
    related_ids: set[str],
) -> bool:
    if isinstance(state, dict):
        for key, value in state.items():
            if key == "base_id" and str(value) == str(base_id):
                return True
            if key.endswith("_id") and str(value) in related_ids:
                return True
            if _state_contains_base_reference(value, base_id, related_ids):
                return True
    if isinstance(state, list):
        return any(_state_contains_base_reference(item, base_id, related_ids) for item in state)
    if isinstance(state, str):
        return state in related_ids
    return False


def _record_runtime_audit(
    uow: Stage06RuntimeUnitOfWork,
    *,
    actor: Actor,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    after_state: dict[str, Any],
) -> None:
    record_audit_event(
        getattr(uow, "session", uow),
        trace_id=f"stage06:{entity_type}:{entity_id}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        after_state=sanitize_stage06_audit_state(after_state),
        permission_snapshot=sanitize_stage06_audit_state(
            {"role": actor.role, "actor_type": actor.actor_type}
        ),
    )


def _require_employee(
    uow: Stage06RuntimeUnitOfWork,
    employee_id: UUID,
) -> DigitalEmployee:
    employee = uow.get_digital_employee(employee_id)
    if employee is None:
        raise PlatformValidationError("digital_employee_not_found", str(employee_id))
    if employee.status != "active":
        raise PlatformValidationError("digital_employee_disabled", str(employee_id))
    return employee


def _require_employee_for_update(
    uow: Stage06RuntimeUnitOfWork,
    employee_id: UUID,
) -> DigitalEmployee:
    employee = uow.get_digital_employee(employee_id)
    if employee is None:
        raise PlatformValidationError("digital_employee_not_found", str(employee_id))
    return employee


def _require_draft(
    uow: Stage06RuntimeUnitOfWork,
    draft_id: UUID,
) -> RecordChangeDraft:
    draft = uow.get_record_change_draft(draft_id)
    if draft is None:
        raise PlatformValidationError("record_change_draft_not_found", str(draft_id))
    return draft


def _assert_employee_action(employee: DigitalEmployee, action: str) -> None:
    if action not in set(employee.allowed_actions):
        raise PlatformValidationError("digital_employee_action_denied", action)


def _assert_view_in_scope(employee: DigitalEmployee, view_id: UUID) -> None:
    if str(view_id) not in set(employee.accessible_views):
        raise PlatformValidationError("digital_employee_scope_denied", str(view_id))


def _assert_table_in_scope(employee: DigitalEmployee, table_id: UUID) -> None:
    if str(table_id) not in set(employee.accessible_tables):
        raise PlatformValidationError("digital_employee_scope_denied", str(table_id))


def _validate_employee_scope(
    uow: Stage06RuntimeUnitOfWork,
    *,
    base_id: UUID,
    accessible_tables: list[str],
    accessible_views: list[str],
) -> None:
    for value in accessible_tables:
        table_id = _scope_uuid(value)
        table = uow.get_table(table_id)
        if table is None:
            raise PlatformValidationError("table_not_found", value)
        if table.base_id != base_id:
            raise PlatformValidationError("resource_scope_mismatch", "employee_table_base")
    for value in accessible_views:
        view_id = _scope_uuid(value)
        view = uow.get_view(view_id)
        if view is None:
            raise PlatformValidationError("view_not_found", value)
        if view.base_id != base_id:
            raise PlatformValidationError("resource_scope_mismatch", "employee_view_base")


def _scope_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise PlatformValidationError("invalid_uuid", str(value)) from exc


def _find_binding(
    uow: Stage06RuntimeUnitOfWork,
    telegram_chat_id: str,
    telegram_user_id: str,
) -> Stage06TelegramBinding | None:
    return next(
        (
            binding
            for binding in uow.list_telegram_bindings()
            if binding.telegram_chat_id == telegram_chat_id
            and binding.telegram_user_id == telegram_user_id
            and binding.status == "active"
        ),
        None,
    )


def _resolve_employee_for_binding(
    uow: Stage06RuntimeUnitOfWork,
    binding: Stage06TelegramBinding,
    alias: str,
) -> DigitalEmployee:
    if binding.default_digital_employee_id is not None:
        employee = uow.get_digital_employee(binding.default_digital_employee_id)
        if employee is not None and employee.telegram_alias == alias:
            return employee
    if binding.default_base_id is not None:
        for employee in uow.list_digital_employees(binding.default_base_id):
            if employee.telegram_alias == alias:
                return employee
    raise PlatformValidationError("digital_employee_not_found", alias)


def _action_from_text(text: str) -> str:
    lowered = text.lower()
    if "summary" in lowered or "summarize" in lowered or "总结" in lowered:
        return "summarize"
    return "summarize"


def _intersect_scope(
    employee_scope: list[str],
    telegram_scope: list[str] | None,
) -> list[str]:
    if telegram_scope is None:
        return list(employee_scope)
    telegram_values = set(telegram_scope)
    return [value for value in employee_scope if value in telegram_values]


def _visible_field_keys(records: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for record in records:
        fields = record.get("fields", {})
        if not isinstance(fields, dict):
            continue
        for key in fields:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def _notification_status(
    *,
    target: dict[str, Any],
    send_policy: dict[str, Any],
    server_mode: str,
    server_allowlist: tuple[str, ...],
) -> str:
    if server_mode in {"disabled", "dry_run"}:
        return "blocked"
    if server_mode != "restricted_test":
        return "blocked"
    chat_id = target.get("telegram_chat_id")
    allowed_targets = set(server_allowlist)
    if not allowed_targets or chat_id not in allowed_targets:
        return "blocked"
    request_allowlist = set(send_policy.get("allowlist") or [])
    if request_allowlist and chat_id not in request_allowlist:
        return "blocked"
    if send_policy.get("dry_run") is True:
        return "blocked"
    if send_policy.get("confirmation") == "required":
        return "pending_confirmation"
    return "queued"


def _safe_output_summary(output: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in output.items()
        if key not in {"records"}
    } | {"record_count": output.get("record_count")}
