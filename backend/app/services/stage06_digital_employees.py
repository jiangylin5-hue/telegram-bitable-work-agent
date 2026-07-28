import re
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.adapters.llm_openrouter import OpenRouterStructuredLLMClient
from app.agents.interfaces import StructuredLLMClient, StructuredLLMResult
from app.agents.stage06_live_digital_employee import (
    run_stage06_live_employee,
    validate_stage06_live_citations,
)
from app.agents.stage06_skill_matching import build_stage06_skill_evidence
from app.models.agent import AgentRun
from app.models.stage06_platform import Stage06TelegramBinding, WorkspaceMember
from app.models.stage06_runtime import (
    DigitalEmployee,
    NotificationRequest,
    RecordChangeDraft,
)
from app.runtime.stage08_collaboration_contracts import (
    Stage08SafeExecutionContext,
    _safe_execution_context_snapshot,
    _stage08_safe_execution_summary,
)
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_audit import sanitize_stage06_audit_state
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    can_actor_write_record_fields,
    create_record,
    get_create_form,
    get_table_schema,
    list_view_records,
    read_base,
    update_record,
)
from app.services.stage09_table_retrieval import (
    answer_covers_result_ticket_codes,
    execute_visible_table_query,
    parse_supported_table_query,
)
from app.services.stage08_memory import enqueue_confirmed_record_memory_event


class Stage06RuntimeUnitOfWork(Stage06PlatformUnitOfWork, Protocol):
    pass


READ_ACTIONS = frozenset({"schema_inspect", "query", "summarize"})
WRITE_LIKE_ACTIONS = frozenset({"draft_create", "draft_update", "status_advance"})
STAGE08_TOOL_CATALOG = (
    "contact.resolve",
    "import.preview",
    "record.query",
    "record_change_draft.create",
    "table.summarize",
    "task.create_draft",
    "tool_catalog.inspect",
)


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
    safe_context: Stage08SafeExecutionContext | None = None,
) -> dict[str, Any]:
    if safe_context is not None:
        _safe_execution_context_snapshot(safe_context)
        if runtime_mode != "deterministic":
            raise PlatformValidationError(
                "stage08_safe_execution_runtime_mode_denied",
                "stage08_safe_execution_runtime_mode_denied",
            )
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
            safe_context=safe_context,
        )
        response["skill_evidence"] = skill_evidence
    else:
        raise PlatformValidationError("unsupported_employee_action", action)

    _record_agent_run(
        uow,
        employee=employee,
        action=action,
        actor=actor,
        output=response,
        safe_context=safe_context,
    )
    _record_runtime_audit(
        uow,
        actor=actor,
        event_type="stage06.digital_employee_invoked",
        entity_type="digital_employee",
        entity_id=employee.id,
        after_state={"action": action, "output": _safe_output_summary(response)},
        safe_context=safe_context,
        safe_action=action,
        safe_counts={"draft_count": int("draft_id" in response)},
        safe_draft_present="draft_id" in response,
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
        # The service produces authoritative result-set citations after the graph.
        # Graph-level validation therefore checks only the JSON envelope; it must
        # not reject an otherwise useful explanation for model-authored IDs.
        "strict_citation_validation": False,
    }
    if action == "draft_update":
        if record_id is None:
            raise PlatformValidationError("record_required", action)
        record = uow.get_record(record_id)
        if record is None:
            raise PlatformValidationError("record_not_found", str(record_id))
        _assert_table_in_scope(employee, record.table_id)

    if action == "summarize" and (
        _policy_refusal_required(skill_evidence) or _sensitive_field_request(prompt)
    ):
        return {
            "action": action,
            "employee_id": str(employee.id),
            "view_id": str(view_id),
            "record_count": 0,
            "records": [],
            "answer": "This field is unavailable.",
            "citations": [],
            "runtime": {"mode": "policy_refusal"},
            "skill_evidence": skill_evidence,
        }

    if action == "summarize" and view_records_override is None:
        intent = parse_supported_table_query(prompt, visible_records)
        if intent is None:
            return {
                "action": action,
                "employee_id": str(employee.id),
                "view_id": str(view_id),
                "record_count": 0,
                "records": [],
                "answer": "Please specify a visible field filter or record identifier.",
                "citations": [],
                "runtime": {"mode": "clarification_required"},
                "skill_evidence": skill_evidence,
            }
        query_result = execute_visible_table_query(intent, visible_records)
        visible_records = list(query_result.records)
        schema = {
            **schema,
            "query_mode": query_result.mode,
            "aggregate_value": query_result.aggregate_value,
            "required_citation_record_ids": list(query_result.record_ids),
        }

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
    if action == "summarize" and view_records_override is None:
        authoritative_answer = _authoritative_query_answer(
            prompt=prompt,
            query_mode=schema.get("query_mode"),
            aggregate_value=schema.get("aggregate_value"),
            records=visible_records,
        )
        content = {
            **content,
            **({"answer": authoritative_answer} if authoritative_answer else {}),
            "citations": _canonical_result_citations(visible_records),
        }
        try:
            validate_stage06_live_citations(
                content.get("citations", []),
                visible_records,
                required_record_ids=schema.get("required_citation_record_ids", []),
            )
        except ValueError as exc:
            raise PlatformValidationError("live_employee_invalid_output", str(exc)) from exc
        if (
            schema.get("query_mode") == "records"
            and not answer_covers_result_ticket_codes(str(content.get("answer", "")), visible_records)
        ):
            raise PlatformValidationError(
                "live_employee_incomplete_answer",
                "result_ticket_code_coverage",
            )
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
                # The model only proposes a change.  The backend has now created the
                # persisted pending draft, so use a stable acknowledgement instead of
                # echoing language that could imply a direct record write occurred.
                "answer": "已提出一个待确认草稿。",
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


def _policy_refusal_required(skill_evidence: dict[str, object]) -> bool:
    selected = skill_evidence.get("selected_skills")
    if not isinstance(selected, list):
        return False
    selected_ids = {
        item.get("skill_id")
        for item in selected
        if isinstance(item, dict) and isinstance(item.get("skill_id"), str)
    }
    if selected_ids == {"platform-shared-policy"}:
        return True
    return any(
        item.get("skill_id") == "platform-shared-policy"
        and item.get("selection") == "selected_guardrail"
        for item in selected
        if isinstance(item, dict)
    )


def _sensitive_field_request(prompt: str | None) -> bool:
    text = (prompt or "").casefold()
    return any(
        marker in text
        for marker in (
            "private_notes",
            "private-notes",
            "private notes",
            "internal_notes",
            "internal-notes",
            "internal notes",
            "restricted_",
            "restricted-",
        )
    )


def _canonical_result_citations(
    records: list[dict[str, Any]],
) -> list[dict[str, object]]:
    """Emit citation IDs from the deterministic result set, never model prose."""

    citations: list[dict[str, object]] = []
    for record in records:
        record_id = record.get("id")
        fields = record.get("fields")
        if not isinstance(record_id, str) or not isinstance(fields, dict):
            continue
        field_keys = ["ticket_code"] if isinstance(fields.get("ticket_code"), str) else []
        if not field_keys:
            field_keys = [key for key in fields if isinstance(key, str)][:1]
        if field_keys:
            citations.append({"record_id": record_id, "field_keys": field_keys})
    return citations


def _authoritative_query_answer(
    *,
    prompt: str | None,
    query_mode: object,
    aggregate_value: object,
    records: list[dict[str, Any]],
) -> str | None:
    """Render supported query facts from the deterministic projection only."""

    codes = [
        fields["ticket_code"]
        for record in records
        if isinstance(record.get("fields"), dict)
        and isinstance((fields := record["fields"]).get("ticket_code"), str)
    ]
    if query_mode == "count" and isinstance(aggregate_value, int):
        suffix = f" Supporting records: {', '.join(codes)}." if codes else ""
        return f"Count: {aggregate_value}.{suffix}"
    if query_mode != "records" or not codes:
        identifier = re.search(r"\b[A-Z][A-Z0-9]*-\d{3,}\b", prompt or "", re.IGNORECASE)
        return f"{identifier.group(0).upper()} was not found." if identifier else None
    entries: list[str] = []
    for record in records:
        fields = record.get("fields")
        if not isinstance(fields, dict) or not isinstance(fields.get("ticket_code"), str):
            continue
        entries.append(
            f"{fields['ticket_code']}: status={fields.get('status', '')}; "
            f"risk_level={fields.get('risk_level', '')}; summary={fields.get('summary', '')}"
        )
    return "\n".join(entries)


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
    draft = _require_draft_transition_lock(uow, draft_id)
    if draft.status != "pending_confirmation":
        raise PlatformValidationError("record_change_draft_invalid_state", str(draft_id))
    if draft.draft_type == "create_record":
        if draft.record_id is not None:
            raise PlatformValidationError("record_change_draft_invalid_state", str(draft_id))
        confirmation_actor = _assert_create_record_confirmation_allowed(uow, draft, actor)
        record = create_record(
            uow,
            draft.table_id,
            values=draft.proposed_values,
            actor=confirmation_actor,
        )
        draft.record_id = record.id
        confirmed_actor = confirmation_actor
    elif draft.draft_type == "update_record":
        if draft.record_id is None:
            raise PlatformValidationError("record_change_draft_missing_record", str(draft_id))
        update_record(
            uow,
            draft.record_id,
            values=draft.proposed_values,
            expected_version=draft.expected_version,
            actor=actor,
        )
        confirmed_actor = actor
    else:
        raise PlatformValidationError("record_change_draft_type_invalid", draft.draft_type)
    if draft.record_id is None:
        raise PlatformValidationError("record_change_draft_missing_record", str(draft_id))
    draft.status = "confirmed"
    _record_runtime_audit(
        uow,
        actor=confirmed_actor,
        event_type="stage06.record_change_draft_confirmed",
        entity_type="record_change_draft",
        entity_id=draft.id,
        after_state={"record_id": str(draft.record_id), "status": draft.status},
    )
    record = uow.get_record(draft.record_id)
    if record is not None:
        enqueue_confirmed_record_memory_event(
            uow,
            draft,
            record,
            confirmation_actor=confirmed_actor,
            now=datetime.now(UTC),
        )
    return draft


def resolve_active_workspace_member(
    uow: Stage06RuntimeUnitOfWork,
    workspace_id: UUID,
    workspace_member_id: UUID,
) -> object:
    member = uow.get_workspace_member(workspace_member_id)
    if (
        member is None
        or member.workspace_id != workspace_id
        or member.status != "active"
    ):
        raise PlatformValidationError("resource_scope_mismatch", "workspace_member")
    return member


def get_stage08_tool_catalog() -> tuple[str, ...]:
    return STAGE08_TOOL_CATALOG


def create_create_record_draft(
    uow: Stage06RuntimeUnitOfWork,
    employee_id: UUID,
    *,
    table_id: UUID,
    proposed_values: dict[str, Any],
    actor: Actor,
    safe_context: Stage08SafeExecutionContext | None = None,
) -> RecordChangeDraft:
    safe_snapshot = (
        None
        if safe_context is None
        else _safe_execution_context_snapshot(safe_context)
    )
    employee = _require_employee(uow, employee_id)
    _assert_employee_action(employee, "draft_create")
    _assert_table_in_scope(employee, table_id)
    table = uow.get_table(table_id)
    if table is None:
        raise PlatformValidationError("table_not_found", str(table_id))
    base = read_base(uow, table.base_id)
    if base.workspace_id != employee.workspace_id:
        raise PlatformValidationError("resource_scope_mismatch", "employee_table_workspace")
    canonical_actor = _canonical_active_member_actor(uow, base.workspace_id, actor)
    create_form = get_create_form(uow, table_id, actor=canonical_actor)
    writable_field_keys = {
        field["key"]
        for field in create_form["fields"]
        if isinstance(field.get("key"), str)
    }
    if not create_form["can_create"] or not set(proposed_values).issubset(writable_field_keys):
        raise PlatformValidationError("record_create_permission_denied", str(table_id))
    draft = RecordChangeDraft(
        id=uuid4(),
        workspace_id=base.workspace_id,
        base_id=base.id,
        table_id=table.id,
        record_id=None,
        draft_type="create_record",
        proposed_values=dict(proposed_values),
        before_values=None,
        created_by_type="digital_employee",
        created_by_id=str(employee.id),
        status="pending_confirmation",
        confirmation_policy=employee.confirmation_policy,
        trace_id=(
            safe_snapshot.trace_hash
            if safe_snapshot is not None
            else f"stage06:draft:{uuid4()}"
        ),
        expected_version=1,
    )
    uow.add_record_change_draft(draft)
    _record_runtime_audit(
        uow,
        actor=canonical_actor,
        event_type="stage06.record_change_draft_created",
        entity_type="record_change_draft",
        entity_id=draft.id,
        after_state={"table_id": str(table.id), "status": draft.status},
        safe_context=safe_context,
        safe_action="task.create_draft",
        safe_status=draft.status,
        safe_counts={"draft_count": 1},
        safe_draft_present=True,
    )
    return draft


def reject_record_change_draft(
    uow: Stage06RuntimeUnitOfWork,
    draft_id: UUID,
    *,
    actor: Actor,
) -> RecordChangeDraft:
    draft = _require_draft_transition_lock(uow, draft_id)
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
    safe_context: Stage08SafeExecutionContext | None = None,
) -> dict[str, Any]:
    safe_snapshot = (
        None
        if safe_context is None
        else _safe_execution_context_snapshot(safe_context)
    )
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
        trace_id=(
            safe_snapshot.trace_hash
            if safe_snapshot is not None
            else f"stage06:draft:{uuid4()}"
        ),
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
        safe_context=safe_context,
        safe_action="record_change_draft.create",
        safe_status=draft.status,
        safe_counts={"draft_count": 1},
        safe_draft_present=True,
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
    safe_context: Stage08SafeExecutionContext | None = None,
) -> None:
    now = datetime.now(UTC)
    if safe_context is not None:
        summary = _stage08_safe_execution_summary(
            safe_context,
            graph="stage08_collaboration_e3",
            status="succeeded",
            action=action,
            counts={"draft_count": int("draft_id" in output)},
            code=None,
            latency_ms=0,
            ticket_present=True,
            draft_present="draft_id" in output,
        )
        uow.add_agent_run(
            AgentRun(
                id=uuid4(),
                agent_name="stage08_safe_execution",
                graph_name="stage08_collaboration_e3",
                model_provider="controlled",
                model_name="deterministic_tool_gateway",
                prompt_version="stage08-e3-safe",
                input_summary=summary,
                output_summary=summary,
                tool_calls=[summary],
                status="succeeded",
                trace_id=_safe_execution_context_snapshot(safe_context).trace_hash,
                started_at=now,
                completed_at=now,
                usage_summary=None,
                cost_summary=None,
                latency_ms=0,
                created_entity_refs=[],
                redaction_policy="stage08_e3_whitelist",
            )
        )
        return
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
    safe_context: Stage08SafeExecutionContext | None = None,
    safe_action: str | None = None,
    safe_status: str = "succeeded",
    safe_counts: dict[str, int] | None = None,
    safe_draft_present: bool = False,
) -> None:
    if safe_context is not None:
        record_audit_event(
            getattr(uow, "session", uow),
            trace_id=_safe_execution_context_snapshot(safe_context).trace_hash,
            actor_type="system",
            actor_id="stage08_e3_safe",
            event_type=event_type,
            entity_type="stage08_safe_execution",
            entity_id=None,
            after_state=_stage08_safe_execution_summary(
                safe_context,
                graph="stage08_collaboration_e3",
                status=safe_status,
                action=safe_action or "safe_execution",
                counts=safe_counts or {},
                code=None,
                latency_ms=0,
                ticket_present=True,
                draft_present=safe_draft_present,
            ),
            permission_snapshot=None,
        )
        return
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


def _require_active_actor_member(
    uow: Stage06RuntimeUnitOfWork,
    workspace_id: UUID,
    actor: Actor,
) -> WorkspaceMember:
    member = next(
        (
            candidate
            for candidate in uow.list_workspace_members(workspace_id)
            if candidate.user_id == actor.actor_id and candidate.status == "active"
        ),
        None,
    )
    if member is None:
        raise PlatformValidationError("actor_not_workspace_member", actor.actor_id)
    return member


def _canonical_active_member_actor(
    uow: Stage06RuntimeUnitOfWork,
    workspace_id: UUID,
    actor: Actor,
) -> Actor:
    member = _require_active_actor_member(uow, workspace_id, actor)
    return Actor(actor_type="user", actor_id=member.user_id, role=member.role)


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


def _require_draft_transition_lock(
    uow: Stage06RuntimeUnitOfWork,
    draft_id: UUID,
) -> RecordChangeDraft:
    draft = uow.lock_record_change_draft_for_transition(draft_id)
    if draft is None:
        raise PlatformValidationError("record_change_draft_not_found", str(draft_id))
    return draft


def _assert_create_record_confirmation_allowed(
    uow: Stage06RuntimeUnitOfWork,
    draft: RecordChangeDraft,
    actor: Actor,
) -> Actor:
    table = uow.get_table(draft.table_id)
    if table is None:
        raise PlatformValidationError("table_not_found", str(draft.table_id))
    base = read_base(uow, table.base_id)
    if base.id != draft.base_id or base.workspace_id != draft.workspace_id:
        raise PlatformValidationError("resource_scope_mismatch", "record_change_draft_table")
    canonical_actor = _canonical_active_member_actor(uow, draft.workspace_id, actor)
    create_form = get_create_form(uow, draft.table_id, actor=canonical_actor)
    if (
        not create_form["can_create"]
        or not can_actor_write_record_fields(
            uow,
            draft.table_id,
            draft.proposed_values.keys(),
            actor=canonical_actor,
        )
    ):
        raise PlatformValidationError("record_create_permission_denied", str(draft.table_id))
    return canonical_actor


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
