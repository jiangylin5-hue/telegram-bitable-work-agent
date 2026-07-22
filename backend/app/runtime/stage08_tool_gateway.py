from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.models.stage08_runtime import Stage08ExecutionTicket
from app.runtime.stage08_collaboration_contracts import (
    Stage08SafeExecutionContext,
    _safe_execution_context_snapshot,
    _stage08_safe_execution_summary,
)
from app.runtime.stage08_contracts import ExecutionTicketState, RedactedToolResult, ToolInvocation, ToolName
from app.services.permissions import Actor
from app.services.stage06_digital_employees import (
    create_create_record_draft,
    get_stage08_tool_catalog,
    invoke_digital_employee,
    resolve_active_workspace_member,
)
from app.services.stage06_platform import PlatformValidationError, Stage06PlatformUnitOfWork
from app.services.stage06_templates import read_import_job
from app.services.stage08_runtime import transition_execution_ticket


_TOOL_ACTIONS: dict[ToolName, str] = {
    "record.query": "query",
    "table.summarize": "summarize",
    "contact.resolve": "contact.resolve",
    "import.preview": "import.preview",
    "tool_catalog.inspect": "tool_catalog.inspect",
    "task.create_draft": "draft_create",
    "record_change_draft.create": "draft_update",
}
_SENSITIVE_INPUT_KEYS = frozenset({"prompt", "response", "api_key", "token", "raw_text"})


class Stage08ToolGatewayError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Stage08ToolGateway:
    def __init__(self) -> None:
        self._registry: dict[str, Callable[[Stage06PlatformUnitOfWork, Stage08ExecutionTicket, Actor, Any], RedactedToolResult]] = {
            "record.query": self._record_query,
            "table.summarize": self._table_summarize,
            "contact.resolve": self._contact_resolve,
            "import.preview": self._import_preview,
            "tool_catalog.inspect": self._tool_catalog_inspect,
            "task.create_draft": self._task_create_draft,
            "record_change_draft.create": self._record_change_draft_create,
        }

    def execute(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        invocation: ToolInvocation,
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> RedactedToolResult:
        if safe_context is not None:
            _safe_execution_context_snapshot(safe_context)
        tool_name = invocation.tool_name
        tracked = self._locked_planned_ticket(uow, ticket.id)
        try:
            actor = self._begin(
                uow,
                tracked,
                tool_name,
                safe_context=safe_context,
            )
        except Stage08ToolGatewayError as exc:
            self._complete_denied(
                uow,
                tracked,
                tool_name,
                exc.code,
                safe_context=safe_context,
            )
            raise
        try:
            result = self._invoke_registered(
                uow,
                tracked,
                actor,
                tool_name,
                invocation.input,
                safe_context=safe_context,
            )
        except Stage08ToolGatewayError as exc:
            self._complete_denied(
                uow,
                tracked,
                tool_name,
                exc.code,
                safe_context=safe_context,
            )
            raise
        except PlatformValidationError as exc:
            self._complete_denied(
                uow,
                tracked,
                tool_name,
                _platform_error_code(exc),
                safe_context=safe_context,
            )
            raise Stage08ToolGatewayError(_platform_error_code(exc)) from None
        except Exception:
            self._complete_failed(
                uow,
                tracked,
                tool_name,
                safe_context=safe_context,
            )
            raise Stage08ToolGatewayError("tool_execution_failed") from None
        result = _safe_tool_result(result) if safe_context is not None else result
        tracked.tool_summary = [
            *tracked.tool_summary,
            (
                _safe_tool_summary(safe_context, result)
                if safe_context is not None
                else result.model_dump()
            ),
        ]
        transition_execution_ticket(
            uow,
            tracked,
            ExecutionTicketState.succeeded,
            safe_context=safe_context,
        )
        return result

    def execute_plan(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        invocations: list[ToolInvocation],
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> Stage08ExecutionTicket:
        """Execute an approved plan under one transition lock and one ticket."""
        if safe_context is not None:
            _safe_execution_context_snapshot(safe_context)
        tracked = self._locked_planned_ticket(uow, ticket.id)
        try:
            actor = self._begin_plan(
                uow,
                tracked,
                invocations,
                safe_context=safe_context,
            )
        except Stage08ToolGatewayError as exc:
            self._complete_denied(
                uow,
                tracked,
                tracked.action,
                exc.code,
                safe_context=safe_context,
            )
            return tracked

        for invocation in invocations:
            tool_name = invocation.tool_name
            try:
                self._authorize_plan_tool(uow, tracked, tool_name)
                result = self._invoke_registered(
                    uow,
                    tracked,
                    actor,
                    tool_name,
                    invocation.input,
                    safe_context=safe_context,
                )
            except Stage08ToolGatewayError as exc:
                self._complete_denied(
                    uow,
                    tracked,
                    tool_name,
                    exc.code,
                    safe_context=safe_context,
                )
                return tracked
            except PlatformValidationError as exc:
                self._complete_denied(
                    uow,
                    tracked,
                    tool_name,
                    _platform_error_code(exc),
                    safe_context=safe_context,
                )
                return tracked
            except Exception:
                self._complete_failed(
                    uow,
                    tracked,
                    tool_name,
                    safe_context=safe_context,
                )
                return tracked
            result = _safe_tool_result(result) if safe_context is not None else result
            tracked.tool_summary = [
                *tracked.tool_summary,
                (
                    _safe_tool_summary(safe_context, result)
                    if safe_context is not None
                    else result.model_dump()
                ),
            ]

        transition_execution_ticket(
            uow,
            tracked,
            ExecutionTicketState.succeeded,
            safe_context=safe_context,
        )
        return tracked

    def _begin(
        self,
        uow: Stage06PlatformUnitOfWork,
        tracked: Stage08ExecutionTicket,
        tool_name: str,
        *,
        safe_context: Stage08SafeExecutionContext | None,
    ) -> Actor:
        transition_execution_ticket(
            uow,
            tracked,
            ExecutionTicketState.executing,
            safe_context=safe_context,
        )
        if tool_name not in _TOOL_ACTIONS:
            raise Stage08ToolGatewayError("tool_not_registered")
        if tracked.action != tool_name:
            raise Stage08ToolGatewayError("policy_denied")
        employee = uow.get_digital_employee(tracked.employee_id)
        if (
            employee is None
            or employee.status != "active"
            or employee.workspace_id != tracked.workspace_id
            or _TOOL_ACTIONS[tool_name] not in set(employee.allowed_actions)
        ):
            raise Stage08ToolGatewayError("policy_denied")
        actor = _actor_for_ticket(uow, tracked)
        return actor

    def _begin_plan(
        self,
        uow: Stage06PlatformUnitOfWork,
        tracked: Stage08ExecutionTicket,
        invocations: list[ToolInvocation],
        *,
        safe_context: Stage08SafeExecutionContext | None,
    ) -> Actor:
        transition_execution_ticket(
            uow,
            tracked,
            ExecutionTicketState.executing,
            safe_context=safe_context,
        )
        if not invocations or tracked.action not in _TOOL_ACTIONS:
            raise Stage08ToolGatewayError("policy_denied")
        if tracked.action not in {invocation.tool_name for invocation in invocations}:
            raise Stage08ToolGatewayError("policy_denied")
        self._authorized_employee(uow, tracked, tracked.action)
        return _actor_for_ticket(uow, tracked)

    def _authorize_plan_tool(
        self,
        uow: Stage06PlatformUnitOfWork,
        tracked: Stage08ExecutionTicket,
        tool_name: str,
    ) -> None:
        self._authorized_employee(uow, tracked, tool_name)

    def _invoke_registered(
        self,
        uow: Stage06PlatformUnitOfWork,
        tracked: Stage08ExecutionTicket,
        actor: Actor,
        tool_name: ToolName,
        value: Any,
        *,
        safe_context: Stage08SafeExecutionContext | None,
    ) -> RedactedToolResult:
        handler = self._registry[tool_name]
        if safe_context is None:
            return handler(uow, tracked, actor, value)
        return handler(
            uow,
            tracked,
            actor,
            value,
            safe_context=safe_context,
        )

    def _authorized_employee(
        self,
        uow: Stage06PlatformUnitOfWork,
        tracked: Stage08ExecutionTicket,
        tool_name: str,
    ) -> None:
        if tool_name not in _TOOL_ACTIONS or tool_name not in self._registry:
            raise Stage08ToolGatewayError("tool_not_registered")
        employee = uow.get_digital_employee(tracked.employee_id)
        if (
            employee is None
            or employee.status != "active"
            or employee.workspace_id != tracked.workspace_id
            or _TOOL_ACTIONS[tool_name] not in set(employee.allowed_actions)
        ):
            raise Stage08ToolGatewayError("policy_denied")

    def _locked_planned_ticket(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket_id: UUID,
    ) -> Stage08ExecutionTicket:
        if not isinstance(ticket_id, UUID):
            raise Stage08ToolGatewayError("ticket_not_found")
        tracked = uow.lock_execution_ticket_for_transition(ticket_id)
        if tracked is None:
            raise Stage08ToolGatewayError("ticket_not_found")
        if tracked.status != ExecutionTicketState.planned.value:
            raise Stage08ToolGatewayError("ticket_not_planned")
        return tracked

    def _complete_denied(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        tool_name: object,
        code: str,
        *,
        safe_context: Stage08SafeExecutionContext | None,
    ) -> None:
        self._append_error_summary(
            ticket,
            tool_name,
            "denied",
            code,
            safe_context=safe_context,
        )
        transition_execution_ticket(
            uow,
            ticket,
            ExecutionTicketState.denied,
            safe_context=safe_context,
        )

    def _complete_failed(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        tool_name: object,
        *,
        safe_context: Stage08SafeExecutionContext | None,
    ) -> None:
        self._append_error_summary(
            ticket,
            tool_name,
            "failed",
            "tool_execution_failed",
            safe_context=safe_context,
        )
        transition_execution_ticket(
            uow,
            ticket,
            ExecutionTicketState.failed,
            safe_context=safe_context,
        )

    def _append_error_summary(
        self,
        ticket: Stage08ExecutionTicket,
        tool_name: object,
        status: str,
        error_code: str,
        *,
        safe_context: Stage08SafeExecutionContext | None,
    ) -> None:
        if tool_name not in _TOOL_ACTIONS:
            return
        if safe_context is not None:
            ticket.tool_summary = [
                *ticket.tool_summary,
                _stage08_safe_execution_summary(
                    safe_context,
                    graph="stage08_collaboration_e3",
                    status=status,
                    action=str(tool_name),
                    counts={},
                    code=error_code,
                    latency_ms=0,
                    ticket_present=True,
                    draft_present=False,
                ),
            ]
            return
        ticket.tool_summary = [
            *ticket.tool_summary,
            RedactedToolResult(
                tool_name=tool_name,
                status=status,
                entity_refs=[],
                visible_field_keys=[],
                counts={},
                error_code=error_code,
            ).model_dump(),
        ]

    def _record_query(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        actor: Actor,
        value: Any,
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> RedactedToolResult:
        view_id = _uuid_input(value, "view_id")
        response = invoke_digital_employee(
            uow,
            ticket.employee_id,
            action="query",
            actor=actor,
            view_id=view_id,
            safe_context=safe_context,
        )
        return _view_result("record.query", view_id, response)

    def _table_summarize(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        actor: Actor,
        value: Any,
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> RedactedToolResult:
        view_id = _uuid_input(value, "view_id")
        response = invoke_digital_employee(
            uow,
            ticket.employee_id,
            action="summarize",
            actor=actor,
            view_id=view_id,
            safe_context=safe_context,
        )
        return _view_result("table.summarize", view_id, response)

    def _contact_resolve(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        actor: Actor,
        value: Any,
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> RedactedToolResult:
        del actor, safe_context
        member_id = _uuid_input(value, "workspace_member_id")
        member = resolve_active_workspace_member(uow, ticket.workspace_id, member_id)
        return RedactedToolResult(
            tool_name="contact.resolve",
            status="succeeded",
            entity_refs=[str(member.id)],
            visible_field_keys=[],
            counts={"resolved_count": 1},
            error_code=None,
        )

    def _import_preview(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        actor: Actor,
        value: Any,
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> RedactedToolResult:
        del actor, safe_context
        import_job_id = _uuid_input(value, "import_job_id")
        job = read_import_job(uow, import_job_id)
        if job.workspace_id != ticket.workspace_id or job.status != "awaiting_confirmation":
            raise Stage08ToolGatewayError("policy_denied")
        row_count = len(job.file_ref.get("rows", [])) if isinstance(job.file_ref, dict) else 0
        field_count = len(job.detected_schema) if isinstance(job.detected_schema, list) else 0
        return RedactedToolResult(
            tool_name="import.preview",
            status="succeeded",
            entity_refs=[str(job.id)],
            visible_field_keys=[],
            counts={"row_count": row_count, "field_count": field_count},
            error_code=None,
        )

    def _tool_catalog_inspect(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        actor: Actor,
        value: Any,
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> RedactedToolResult:
        del uow, ticket, actor, safe_context
        _empty_input(value)
        catalog = get_stage08_tool_catalog()
        return RedactedToolResult(
            tool_name="tool_catalog.inspect",
            status="succeeded",
            entity_refs=list(catalog),
            visible_field_keys=[],
            counts={"tool_count": len(catalog)},
            error_code=None,
        )

    def _task_create_draft(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        actor: Actor,
        value: Any,
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> RedactedToolResult:
        table_id, proposed_values = _draft_input(value, "table_id")
        draft = create_create_record_draft(
            uow,
            ticket.employee_id,
            table_id=table_id,
            proposed_values=proposed_values,
            actor=actor,
            safe_context=safe_context,
        )
        return _draft_result("task.create_draft", draft.id, table_id)

    def _record_change_draft_create(
        self,
        uow: Stage06PlatformUnitOfWork,
        ticket: Stage08ExecutionTicket,
        actor: Actor,
        value: Any,
        *,
        safe_context: Stage08SafeExecutionContext | None = None,
    ) -> RedactedToolResult:
        record_id, proposed_values = _draft_input(value, "record_id")
        response = invoke_digital_employee(
            uow,
            ticket.employee_id,
            action="draft_update",
            actor=actor,
            record_id=record_id,
            proposed_values=proposed_values,
            safe_context=safe_context,
        )
        draft_id = _response_uuid(response, "draft_id")
        return _draft_result("record_change_draft.create", draft_id, record_id)


def _safe_tool_result(result: RedactedToolResult) -> RedactedToolResult:
    return RedactedToolResult(
        tool_name=result.tool_name,
        status=result.status,
        entity_refs=[],
        visible_field_keys=[],
        counts=dict(result.counts),
        error_code=result.error_code,
    )


def _safe_tool_summary(
    safe_context: Stage08SafeExecutionContext,
    result: RedactedToolResult,
) -> dict[str, object]:
    return _stage08_safe_execution_summary(
        safe_context,
        graph="stage08_collaboration_e3",
        status=result.status,
        action=result.tool_name,
        counts=dict(result.counts),
        code=result.error_code,
        latency_ms=0,
        ticket_present=True,
        draft_present=result.counts.get("draft_count", 0) > 0,
    )


def _actor_for_ticket(uow: Stage06PlatformUnitOfWork, ticket: Stage08ExecutionTicket) -> Actor:
    if not isinstance(ticket.actor_id, str) or not ticket.actor_id.startswith("user:"):
        raise Stage08ToolGatewayError("policy_denied")
    user_id = ticket.actor_id.removeprefix("user:")
    if not user_id or not user_id.strip():
        raise Stage08ToolGatewayError("policy_denied")
    member = next(
        (
            candidate
            for candidate in uow.list_workspace_members(ticket.workspace_id)
            if candidate.user_id == user_id and candidate.status == "active"
        ),
        None,
    )
    if member is None:
        raise Stage08ToolGatewayError("policy_denied")
    return Actor(actor_type="user", actor_id=user_id, role=member.role)


def _uuid_input(value: Any, key: str) -> UUID:
    if not isinstance(value, dict) or set(value) != {key}:
        raise Stage08ToolGatewayError("invalid_input")
    raw = value.get(key)
    if not isinstance(raw, str):
        raise Stage08ToolGatewayError("invalid_input")
    try:
        return UUID(raw)
    except (TypeError, ValueError):
        raise Stage08ToolGatewayError("invalid_input") from None


def _draft_input(value: Any, id_key: str) -> tuple[UUID, dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {id_key, "proposed_values"}:
        raise Stage08ToolGatewayError("invalid_input")
    record_id = _uuid_input({id_key: value.get(id_key)}, id_key)
    proposed_values = value.get("proposed_values")
    if not isinstance(proposed_values, dict) or not _safe_json_value(proposed_values):
        raise Stage08ToolGatewayError("invalid_input")
    return record_id, dict(proposed_values)


def _empty_input(value: Any) -> None:
    if not isinstance(value, dict) or value:
        raise Stage08ToolGatewayError("invalid_input")


def _safe_json_value(value: Any) -> bool:
    if value is None or type(value) in {str, int, float, bool}:
        return True
    if isinstance(value, list):
        return all(_safe_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str)
            and key.casefold() not in _SENSITIVE_INPUT_KEYS
            and _safe_json_value(item)
            for key, item in value.items()
        )
    return False


def _view_result(tool_name: ToolName, view_id: UUID, response: dict[str, Any]) -> RedactedToolResult:
    records = response.get("records")
    if not isinstance(records, list):
        raise Stage08ToolGatewayError("tool_execution_failed")
    visible_field_keys = sorted(
        {
            key
            for record in records
            if isinstance(record, dict)
            for key in record
            if isinstance(key, str)
        }
    )
    record_count = response.get("record_count")
    if type(record_count) is not int or record_count < 0:
        raise Stage08ToolGatewayError("tool_execution_failed")
    return RedactedToolResult(
        tool_name=tool_name,
        status="succeeded",
        entity_refs=[str(view_id)],
        visible_field_keys=visible_field_keys,
        counts={"record_count": record_count},
        error_code=None,
    )


def _draft_result(tool_name: ToolName, draft_id: UUID, entity_id: UUID) -> RedactedToolResult:
    return RedactedToolResult(
        tool_name=tool_name,
        status="succeeded",
        entity_refs=[str(draft_id), str(entity_id)],
        visible_field_keys=[],
        counts={"draft_count": 1, "confirmation_required": 1},
        error_code=None,
    )


def _response_uuid(response: dict[str, Any], key: str) -> UUID:
    value = response.get(key)
    if not isinstance(value, str):
        raise Stage08ToolGatewayError("tool_execution_failed")
    try:
        return UUID(value)
    except ValueError:
        raise Stage08ToolGatewayError("tool_execution_failed") from None


def _platform_error_code(exc: PlatformValidationError) -> str:
    if exc.code in {"record_not_found", "view_not_found", "table_not_found"}:
        return "not_found"
    if exc.code in {
        "digital_employee_action_denied",
        "digital_employee_scope_denied",
        "record_create_permission_denied",
        "resource_scope_mismatch",
        "actor_not_workspace_member",
    }:
        return "permission_denied"
    return "tool_execution_failed"
