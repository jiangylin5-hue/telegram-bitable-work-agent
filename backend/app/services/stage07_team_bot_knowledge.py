from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import inspect

from app.agents.interfaces import StructuredLLMClient
from app.models.stage06_runtime import DigitalEmployee
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_digital_employees import invoke_digital_employee
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    get_view_presentation,
    list_bases_for_workspace,
    list_view_records,
    list_views_for_base,
)
from app.services.stage07_digital_employee_management import (
    is_member_eligible_for_employee,
)


TEAM_BOT_KNOWLEDGE_ROW_LIMIT = 100
_SAFE_TEAM_BOT_VIEW_TYPES = frozenset({"grid", "kanban", "calendar", "form"})
_TEAM_BOT_OPERATION = "stage07.team_bot.summary"


@dataclass(frozen=True)
class TeamBotKnowledgeWindow:
    employee: DigitalEmployee
    actor: Actor
    view_id: UUID
    records: list[dict[str, Any]]
    truncated: bool


@dataclass(frozen=True)
class TeamBotSummaryReceipt:
    kind: str
    employee_id: UUID
    base_id: UUID
    view_id: UUID
    answer: str
    citation_record_ids: list[str]
    knowledge_window_truncated: bool
    audit_event_id: UUID


def list_team_bot_contacts(
    uow: Stage06PlatformUnitOfWork,
    *,
    workspace_id: UUID,
    actor: Actor,
) -> list[DigitalEmployee]:
    contacts = [
        employee
        for base in list_bases_for_workspace(uow, workspace_id)
        for employee in uow.list_digital_employees(base.id)
        if employee.workspace_id == workspace_id
        and employee.status == "active"
        and "summarize" in set(employee.allowed_actions)
        and is_member_eligible_for_employee(uow, employee, actor.actor_id)
    ]
    contacts.sort(key=lambda employee: (employee.name.casefold(), str(employee.id)))
    return contacts


def resolve_team_bot_context(
    uow: Stage06PlatformUnitOfWork,
    *,
    employee_id: UUID,
    actor: Actor,
) -> tuple[DigitalEmployee, list[Any]]:
    employee = _require_team_bot_employee(uow, employee_id, actor=actor)
    views = _team_bot_views(uow, employee=employee, actor=actor)
    return employee, views


def resolve_team_bot_selected_view(
    uow: Stage06PlatformUnitOfWork,
    *,
    employee_id: UUID,
    view_id: UUID,
    actor: Actor,
) -> tuple[DigitalEmployee, Any]:
    employee, views = resolve_team_bot_context(
        uow,
        employee_id=employee_id,
        actor=actor,
    )
    view = next((candidate for candidate in views if candidate.id == view_id), None)
    if view is None:
        raise PlatformValidationError("team_bot_context_not_found", str(employee_id))
    return employee, view


def build_team_bot_knowledge_window(
    uow: Stage06PlatformUnitOfWork,
    *,
    employee_id: UUID,
    base_id: UUID,
    view_id: UUID,
    actor: Actor,
) -> TeamBotKnowledgeWindow:
    employee, _view = resolve_team_bot_selected_view(
        uow,
        employee_id=employee_id,
        view_id=view_id,
        actor=actor,
    )
    if base_id != employee.base_id:
        raise PlatformValidationError("team_bot_context_not_found", str(employee_id))
    payload = list_view_records(
        uow,
        view_id,
        actor=actor,
        limit=TEAM_BOT_KNOWLEDGE_ROW_LIMIT + 1,
    )
    permitted = [
        {"id": record["id"], "fields": dict(record["fields"])}
        for record in payload.get("records", [])
        if isinstance(record, dict)
        and isinstance(record.get("id"), str)
        and isinstance(record.get("fields"), dict)
    ]
    return TeamBotKnowledgeWindow(
        employee=employee,
        actor=actor,
        view_id=view_id,
        records=permitted[:TEAM_BOT_KNOWLEDGE_ROW_LIMIT],
        truncated=len(permitted) > TEAM_BOT_KNOWLEDGE_ROW_LIMIT,
    )


def summarize_team_bot_knowledge(
    uow: Stage06PlatformUnitOfWork,
    *,
    employee_id: UUID,
    base_id: UUID,
    view_id: UUID,
    actor: Actor,
    instruction: str | None,
    idempotency_key: str,
    llm_client: StructuredLLMClient | None = None,
) -> TeamBotSummaryReceipt:
    window = build_team_bot_knowledge_window(
        uow,
        employee_id=employee_id,
        base_id=base_id,
        view_id=view_id,
        actor=actor,
    )
    normalized_instruction = _normalized_instruction(instruction)
    fingerprint = fingerprint_request(
        {
            "operation": _TEAM_BOT_OPERATION,
            "workspace_id": str(window.employee.workspace_id),
            "actor_id": actor.actor_id,
            "employee_id": str(window.employee.id),
            "base_id": str(base_id),
            "view_id": str(view_id),
            "instruction": normalized_instruction,
        }
    )
    decision = begin_idempotent_operation(
        uow,
        workspace_id=window.employee.workspace_id,
        operation=_TEAM_BOT_OPERATION,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        trace_id=idempotency_trace_id(_TEAM_BOT_OPERATION, fingerprint, idempotency_key),
    )
    if decision.status == "replay":
        return _receipt_from_idempotency_replay(decision.response_ref)

    if not window.records:
        receipt = TeamBotSummaryReceipt(
            kind="empty_context",
            employee_id=window.employee.id,
            base_id=base_id,
            view_id=view_id,
            answer="当前视图没有可供团队 Bot 汇总的记录。",
            citation_record_ids=[],
            knowledge_window_truncated=False,
            audit_event_id=_record_team_bot_audit(
                uow,
                actor=actor,
                employee=window.employee,
                view_id=view_id,
                row_count=0,
                truncated=False,
                outcome="empty_context",
            ),
        )
    else:
        try:
            result = invoke_digital_employee(
                uow,
                window.employee.id,
                action="summarize",
                actor=actor,
                view_id=view_id,
                runtime_mode="live_openrouter",
                prompt=normalized_instruction,
                llm_client=llm_client,
                view_records_override=window.records,
            )
        except Exception:
            _discard_team_bot_idempotency_reservation(uow, decision.record)
            raise
        answer = result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise PlatformValidationError("team_bot_summary_unavailable", str(employee_id))
        receipt = TeamBotSummaryReceipt(
            kind="summary",
            employee_id=window.employee.id,
            base_id=base_id,
            view_id=view_id,
            answer=answer,
            citation_record_ids=_safe_window_citations(
                result.get("citations"),
                visible_records=window.records,
            ),
            knowledge_window_truncated=window.truncated,
            audit_event_id=_record_team_bot_audit(
                uow,
                actor=actor,
                employee=window.employee,
                view_id=view_id,
                row_count=len(window.records),
                truncated=window.truncated,
                outcome="summary",
            ),
        )

    complete_idempotent_operation(
        decision.record,
        response_ref=_receipt_response_ref(receipt),
    )
    return receipt


def _require_team_bot_employee(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
    *,
    actor: Actor,
) -> DigitalEmployee:
    employee = uow.get_digital_employee(employee_id)
    if (
        employee is None
        or employee.status != "active"
        or "summarize" not in set(employee.allowed_actions)
        or not is_member_eligible_for_employee(uow, employee, actor.actor_id)
        or employee.base_id not in {
            base.id for base in list_bases_for_workspace(uow, employee.workspace_id)
        }
    ):
        raise PlatformValidationError("team_bot_not_found", str(employee_id))
    return employee


def _team_bot_views(
    uow: Stage06PlatformUnitOfWork,
    *,
    employee: DigitalEmployee,
    actor: Actor,
) -> list[Any]:
    scoped_view_ids = set(employee.accessible_views)
    scoped_table_ids = set(employee.accessible_tables)
    views = []
    for view in list_views_for_base(uow, employee.base_id, actor=actor):
        if (
            str(view.id) not in scoped_view_ids
            or view.table_id is None
            or str(view.table_id) not in scoped_table_ids
            or view.view_type not in _SAFE_TEAM_BOT_VIEW_TYPES
        ):
            continue
        try:
            get_view_presentation(uow, view.id, actor=actor)
        except PlatformValidationError:
            continue
        views.append(view)
    views.sort(key=lambda view: (view.name.casefold(), str(view.id)))
    return views


def _normalized_instruction(instruction: str | None) -> str:
    if instruction is None:
        return ""
    if not isinstance(instruction, str):
        raise PlatformValidationError("team_bot_instruction_invalid", "instruction")
    normalized = instruction.strip()
    if len(normalized) > 600:
        raise PlatformValidationError("team_bot_instruction_invalid", "instruction")
    return normalized


def _safe_window_citations(
    citations: object,
    *,
    visible_records: list[dict[str, Any]],
) -> list[str]:
    if not isinstance(citations, list):
        return []
    visible_record_ids = {
        record["id"]
        for record in visible_records
        if isinstance(record.get("id"), str)
    }
    result: list[str] = []
    seen: set[str] = set()
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        record_id = citation.get("record_id")
        if (
            not isinstance(record_id, str)
            or record_id not in visible_record_ids
            or record_id in seen
        ):
            continue
        result.append(record_id)
        seen.add(record_id)
    return result


def _record_team_bot_audit(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    employee: DigitalEmployee,
    view_id: UUID,
    row_count: int,
    truncated: bool,
    outcome: str,
) -> UUID:
    event = record_audit_event(
        getattr(uow, "session", uow),
        trace_id=f"stage07:team-bot:{employee.id}:{view_id}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type="stage07.team_bot_summary",
        entity_type="digital_employee",
        entity_id=employee.id,
        after_state={
            "employee_id": str(employee.id),
            "base_id": str(employee.base_id),
            "view_id": str(view_id),
            "record_count": row_count,
            "truncated": truncated,
            "outcome": outcome,
        },
        permission_snapshot={
            "actor_type": actor.actor_type,
            "role": actor.role,
            "action": "digital_employee.invoke",
        },
    )
    if event.id is None:
        event.id = uuid4()
    return event.id


def _receipt_response_ref(receipt: TeamBotSummaryReceipt) -> dict[str, object]:
    return {
        "kind": receipt.kind,
        "employee_id": str(receipt.employee_id),
        "base_id": str(receipt.base_id),
        "view_id": str(receipt.view_id),
        "answer": receipt.answer,
        "citation_record_ids": list(receipt.citation_record_ids),
        "knowledge_window_truncated": receipt.knowledge_window_truncated,
        "audit_event_id": str(receipt.audit_event_id),
    }


def _discard_team_bot_idempotency_reservation(
    uow: Stage06PlatformUnitOfWork,
    record: object,
) -> None:
    """Make an unavailable provider retryable before any safe summary receipt exists."""
    session = getattr(uow, "session", None)
    if session is not None:
        state = inspect(record)
        if state.pending:
            session.expunge(record)
        elif state.persistent:
            session.delete(record)
        session.commit()
        return
    records = getattr(uow, "idempotency_records", None)
    if isinstance(records, list) and record in records:
        records.remove(record)


def _receipt_from_idempotency_replay(
    response_ref: dict[str, Any] | None,
) -> TeamBotSummaryReceipt:
    payload = response_ref or {}
    try:
        kind = str(payload["kind"])
        if kind not in {"summary", "empty_context"}:
            raise ValueError("kind")
        answer = payload["answer"]
        citations = payload["citation_record_ids"]
        truncated = payload["knowledge_window_truncated"]
        if (
            not isinstance(answer, str)
            or not isinstance(citations, list)
            or not all(isinstance(item, str) for item in citations)
            or not isinstance(truncated, bool)
        ):
            raise ValueError("payload")
        return TeamBotSummaryReceipt(
            kind=kind,
            employee_id=UUID(str(payload["employee_id"])),
            base_id=UUID(str(payload["base_id"])),
            view_id=UUID(str(payload["view_id"])),
            answer=answer,
            citation_record_ids=list(citations),
            knowledge_window_truncated=truncated,
            audit_event_id=UUID(str(payload["audit_event_id"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PlatformValidationError("team_bot_summary_unavailable", _TEAM_BOT_OPERATION) from exc
