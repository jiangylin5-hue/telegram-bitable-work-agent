from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

from app.models.stage06_runtime import DigitalEmployee, DigitalEmployeeMemberGrant
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_audit import sanitize_stage06_audit_state
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    read_base,
)


MANAGED_ACTIONS: Final = frozenset({"summarize", "draft_update"})
MANAGED_STATUSES: Final = frozenset({"draft", "active", "paused"})
MANAGED_ACCESS_MODES: Final = frozenset({"workspace", "assigned"})
_UNSET: Final = object()


@dataclass(frozen=True)
class ManagedEmployeeCreateCommand:
    name: str
    description: str
    telegram_alias: str | None


@dataclass(frozen=True)
class ManagedEmployeeUpdateCommand:
    name: str | None = None
    description: str | None = None
    telegram_alias: str | None | object = _UNSET
    accessible_table_ids: list[UUID] | None = None
    accessible_view_ids: list[UUID] | None = None
    allowed_actions: list[str] | None = None
    access_mode: str | None = None


@dataclass(frozen=True)
class ManagedEmployeeLifecycleReceipt:
    id: UUID
    status: str
    version: int
    audit_event_id: UUID


def create_managed_employee(
    uow: Stage06PlatformUnitOfWork,
    base_id: UUID,
    *,
    actor: Actor,
    command: ManagedEmployeeCreateCommand,
    idempotency_key: str,
) -> DigitalEmployee:
    base = read_base(uow, base_id)
    _require_active_manager_membership(uow, base.workspace_id, actor)
    name = _normalized_name(command.name)
    description = _normalized_description(command.description)
    alias = _normalized_alias(command.telegram_alias)
    operation = "stage07.digital_employee.create"
    fingerprint = fingerprint_request(
        {
            "operation": operation,
            "base_id": str(base.id),
            "actor_id": actor.actor_id,
            "name": name,
            "description": description,
            "telegram_alias": alias,
        }
    )
    decision = begin_idempotent_operation(
        uow,
        workspace_id=base.workspace_id,
        operation=operation,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        trace_id=idempotency_trace_id(operation, fingerprint, idempotency_key),
    )
    if decision.status == "replay":
        return _employee_from_idempotency_replay(uow, decision.response_ref, operation)

    employee = DigitalEmployee(
        id=uuid4(),
        workspace_id=base.workspace_id,
        base_id=base.id,
        name=name,
        description=description,
        telegram_alias=alias,
        accessible_tables=[],
        accessible_views=[],
        field_policy={},
        allowed_actions=["summarize"],
        confirmation_policy={
            "draft_create": "required",
            "draft_update": "required",
        },
        response_style={},
        status="draft",
        version=1,
        access_mode="assigned",
    )
    uow.add_digital_employee(employee)
    _record_management_audit(
        uow,
        actor=actor,
        event_type="stage07.digital_employee_management_created",
        employee=employee,
        before_status=None,
    )
    complete_idempotent_operation(
        decision.record,
        response_ref={"employee_id": str(employee.id)},
    )
    return employee


def update_managed_employee(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
    *,
    actor: Actor,
    command: ManagedEmployeeUpdateCommand,
    expected_version: int,
) -> DigitalEmployee:
    employee = _locked_managed_employee(uow, employee_id, actor=actor)
    _require_expected_version(employee, expected_version)
    if employee.status == "active":
        raise PlatformValidationError(
            "digital_employee_active_requires_pause",
            str(employee.id),
        )
    _require_managed_mutable_status(employee)

    next_name = employee.name if command.name is None else _normalized_name(command.name)
    next_description = (
        employee.description
        if command.description is None
        else _normalized_description(command.description)
    )
    next_alias = (
        employee.telegram_alias
        if command.telegram_alias is _UNSET
        else _normalized_alias(command.telegram_alias)
    )
    table_ids = (
        _employee_scope_ids(employee.accessible_tables, "table")
        if command.accessible_table_ids is None
        else _normalized_ids(command.accessible_table_ids, "table")
    )
    view_ids = (
        _employee_scope_ids(employee.accessible_views, "view")
        if command.accessible_view_ids is None
        else _normalized_ids(command.accessible_view_ids, "view")
    )
    actions = (
        _normalized_actions(employee.allowed_actions)
        if command.allowed_actions is None
        else _normalized_actions(command.allowed_actions)
    )
    access_mode = (
        _employee_access_mode(employee)
        if command.access_mode is None
        else _normalized_access_mode(command.access_mode)
    )
    _validate_employee_scope(uow, employee, table_ids=table_ids, view_ids=view_ids)

    before_status = employee.status
    employee.name = next_name
    employee.description = next_description
    employee.telegram_alias = next_alias
    employee.accessible_tables = [str(table_id) for table_id in table_ids]
    employee.accessible_views = [str(view_id) for view_id in view_ids]
    employee.allowed_actions = actions
    employee.access_mode = access_mode
    employee.version += 1
    _record_management_audit(
        uow,
        actor=actor,
        event_type="stage07.digital_employee_management_updated",
        employee=employee,
        before_status=before_status,
    )
    return employee


def replace_managed_employee_grants(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
    *,
    actor: Actor,
    member_ids: list[UUID],
    expected_version: int,
    idempotency_key: str,
) -> DigitalEmployee:
    employee = _locked_managed_employee(uow, employee_id, actor=actor)
    operation = "stage07.digital_employee.replace_member_grants"
    normalized_member_ids = _normalized_ids(member_ids, "workspace_member")
    fingerprint = fingerprint_request(
        {
            "operation": operation,
            "employee_id": str(employee.id),
            "expected_version": expected_version,
            "member_ids": [str(member_id) for member_id in normalized_member_ids],
        }
    )
    decision = begin_idempotent_operation(
        uow,
        workspace_id=employee.workspace_id,
        operation=operation,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        trace_id=idempotency_trace_id(operation, fingerprint, idempotency_key),
    )
    if decision.status == "replay":
        return _employee_from_idempotency_replay(uow, decision.response_ref, operation)

    _require_expected_version(employee, expected_version)
    _require_managed_mutable_status(employee)
    _validate_grant_members(uow, employee, normalized_member_ids)
    grants = [
        DigitalEmployeeMemberGrant(
            id=uuid4(),
            employee_id=employee.id,
            workspace_member_id=member_id,
        )
        for member_id in normalized_member_ids
    ]
    before_status = employee.status
    uow.replace_digital_employee_member_grants(employee.id, grants)
    employee.version += 1
    _record_management_audit(
        uow,
        actor=actor,
        event_type="stage07.digital_employee_member_grants_replaced",
        employee=employee,
        before_status=before_status,
        member_count=len(grants),
    )
    complete_idempotent_operation(
        decision.record,
        response_ref={"employee_id": str(employee.id)},
    )
    return employee


def activate_managed_employee(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
    *,
    actor: Actor,
    expected_version: int,
    idempotency_key: str,
) -> ManagedEmployeeLifecycleReceipt:
    employee = _locked_managed_employee(uow, employee_id, actor=actor)
    operation = "stage07.digital_employee.activate"
    decision = _begin_lifecycle_idempotency(
        uow,
        employee=employee,
        actor=actor,
        operation=operation,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
    )
    if decision.status == "replay":
        return _lifecycle_receipt_from_replay(decision.response_ref, operation)

    _require_expected_version(employee, expected_version)
    if employee.status not in {"draft", "paused"}:
        raise PlatformValidationError("digital_employee_activation_state_invalid", employee.status)
    _validate_activation(uow, employee)
    _assert_active_alias_available(uow, employee)
    before_status = employee.status
    employee.status = "active"
    employee.version += 1
    uow.flush()
    audit = _record_management_audit(
        uow,
        actor=actor,
        event_type="stage07.digital_employee_activated",
        employee=employee,
        before_status=before_status,
    )
    receipt = ManagedEmployeeLifecycleReceipt(
        id=employee.id,
        status=employee.status,
        version=employee.version,
        audit_event_id=audit.id,
    )
    complete_idempotent_operation(
        decision.record,
        response_ref=_lifecycle_receipt_response(receipt),
    )
    return receipt


def pause_managed_employee(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
    *,
    actor: Actor,
    expected_version: int,
    idempotency_key: str,
) -> ManagedEmployeeLifecycleReceipt:
    employee = _locked_managed_employee(uow, employee_id, actor=actor)
    operation = "stage07.digital_employee.pause"
    decision = _begin_lifecycle_idempotency(
        uow,
        employee=employee,
        actor=actor,
        operation=operation,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
    )
    if decision.status == "replay":
        return _lifecycle_receipt_from_replay(decision.response_ref, operation)

    _require_expected_version(employee, expected_version)
    if employee.status != "active":
        raise PlatformValidationError("digital_employee_pause_state_invalid", employee.status)
    before_status = employee.status
    employee.status = "paused"
    employee.version += 1
    audit = _record_management_audit(
        uow,
        actor=actor,
        event_type="stage07.digital_employee_paused",
        employee=employee,
        before_status=before_status,
    )
    receipt = ManagedEmployeeLifecycleReceipt(
        id=employee.id,
        status=employee.status,
        version=employee.version,
        audit_event_id=audit.id,
    )
    complete_idempotent_operation(
        decision.record,
        response_ref=_lifecycle_receipt_response(receipt),
    )
    return receipt


def is_member_eligible_for_employee(
    uow: Stage06PlatformUnitOfWork,
    employee: DigitalEmployee,
    actor_user_id: str,
) -> bool:
    if employee.status != "active":
        return False
    access_mode = _employee_access_mode(employee, fail_closed=False)
    if access_mode == "workspace":
        return True
    if access_mode != "assigned":
        return False
    active_member = next(
        (
            member
            for member in uow.list_workspace_members(employee.workspace_id)
            if member.user_id == actor_user_id and member.status == "active"
        ),
        None,
    )
    if active_member is None:
        return False
    return any(
        grant.workspace_member_id == active_member.id
        for grant in uow.list_digital_employee_member_grants(employee.id)
    )


def _locked_managed_employee(
    uow: Stage06PlatformUnitOfWork,
    employee_id: UUID,
    *,
    actor: Actor,
) -> DigitalEmployee:
    employee = uow.lock_digital_employee_for_management(employee_id)
    if employee is None:
        raise PlatformValidationError("digital_employee_not_found", str(employee_id))
    base = read_base(uow, employee.base_id)
    if base.workspace_id != employee.workspace_id:
        raise PlatformValidationError("digital_employee_base_scope_invalid", str(employee.id))
    _require_active_manager_membership(uow, employee.workspace_id, actor)
    return employee


def _require_active_manager_membership(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    actor: Actor,
) -> None:
    if not any(
        member.user_id == actor.actor_id and member.status == "active"
        for member in uow.list_workspace_members(workspace_id)
    ):
        raise PlatformValidationError(
            "digital_employee_manager_membership_required",
            actor.actor_id,
        )


def _require_expected_version(employee: DigitalEmployee, expected_version: int) -> None:
    if expected_version != employee.version:
        raise PlatformValidationError(
            "digital_employee_revision_conflict",
            str(employee.id),
        )


def _require_managed_mutable_status(employee: DigitalEmployee) -> None:
    if employee.status not in {"draft", "paused"}:
        raise PlatformValidationError(
            "digital_employee_management_state_invalid",
            employee.status,
        )


def _validate_activation(
    uow: Stage06PlatformUnitOfWork,
    employee: DigitalEmployee,
) -> None:
    table_ids = _employee_scope_ids(employee.accessible_tables, "table")
    view_ids = _employee_scope_ids(employee.accessible_views, "view")
    actions = _normalized_actions(employee.allowed_actions)
    access_mode = _employee_access_mode(employee)
    _validate_employee_scope(uow, employee, table_ids=table_ids, view_ids=view_ids)
    if not view_ids:
        raise PlatformValidationError("digital_employee_view_required", str(employee.id))
    if "summarize" not in actions:
        raise PlatformValidationError("digital_employee_summarize_required", str(employee.id))
    if access_mode == "assigned":
        grants = uow.list_digital_employee_member_grants(employee.id)
        if not grants:
            raise PlatformValidationError(
                "digital_employee_member_grant_required",
                str(employee.id),
            )
        _validate_grant_members(
            uow,
            employee,
            [grant.workspace_member_id for grant in grants],
        )


def _validate_employee_scope(
    uow: Stage06PlatformUnitOfWork,
    employee: DigitalEmployee,
    *,
    table_ids: list[UUID],
    view_ids: list[UUID],
) -> None:
    table_id_set = set(table_ids)
    for table_id in table_ids:
        table = uow.get_table(table_id)
        if table is None or table.base_id != employee.base_id or table.status != "active":
            raise PlatformValidationError("digital_employee_scope_denied", "table")
    for view_id in view_ids:
        view = uow.get_view(view_id)
        if (
            view is None
            or view.base_id != employee.base_id
            or view.table_id not in table_id_set
            or view.status != "active"
        ):
            raise PlatformValidationError("digital_employee_scope_denied", "view")


def _validate_grant_members(
    uow: Stage06PlatformUnitOfWork,
    employee: DigitalEmployee,
    member_ids: list[UUID],
) -> None:
    for member_id in member_ids:
        member = uow.get_workspace_member(member_id)
        if member is None or member.workspace_id != employee.workspace_id:
            raise PlatformValidationError(
                "digital_employee_member_scope_denied",
                str(member_id),
            )
        if member.status != "active":
            raise PlatformValidationError(
                "digital_employee_member_inactive",
                str(member_id),
            )


def _assert_active_alias_available(
    uow: Stage06PlatformUnitOfWork,
    employee: DigitalEmployee,
) -> None:
    if employee.telegram_alias is None:
        return
    if any(
        existing.id != employee.id
        and existing.status == "active"
        and existing.telegram_alias == employee.telegram_alias
        for existing in uow.list_digital_employees(employee.base_id)
    ):
        raise PlatformValidationError(
            "digital_employee_alias_conflict",
            employee.telegram_alias,
        )


def _normalized_name(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 160:
        raise PlatformValidationError("digital_employee_name_invalid", "name")
    return normalized


def _normalized_description(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 500:
        raise PlatformValidationError("digital_employee_description_invalid", "description")
    return normalized


def _normalized_alias(value: str | None | object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PlatformValidationError("digital_employee_alias_invalid", "telegram_alias")
    normalized = value.strip()
    if not normalized or len(normalized) > 80:
        raise PlatformValidationError("digital_employee_alias_invalid", "telegram_alias")
    return normalized


def _normalized_access_mode(value: str) -> str:
    if value not in MANAGED_ACCESS_MODES:
        raise PlatformValidationError("digital_employee_access_mode_unsupported", value)
    return value


def _employee_access_mode(
    employee: DigitalEmployee,
    *,
    fail_closed: bool = True,
) -> str | None:
    value = employee.access_mode or "workspace"
    if value not in MANAGED_ACCESS_MODES:
        if fail_closed:
            raise PlatformValidationError("digital_employee_access_mode_unsupported", value)
        return None
    return value


def _normalized_actions(actions: list[str]) -> list[str]:
    if len(actions) != len(set(actions)):
        raise PlatformValidationError("digital_employee_action_duplicate", "allowed_actions")
    unsupported = set(actions).difference(MANAGED_ACTIONS)
    if unsupported:
        raise PlatformValidationError(
            "digital_employee_action_unsupported",
            sorted(unsupported)[0],
        )
    return sorted(actions)


def _normalized_ids(values: list[UUID], resource_type: str) -> list[UUID]:
    if len(values) != len(set(values)):
        raise PlatformValidationError(
            "digital_employee_scope_duplicate",
            resource_type,
        )
    return sorted(values, key=str)


def _employee_scope_ids(values: list[str], resource_type: str) -> list[UUID]:
    try:
        return _normalized_ids([UUID(str(value)) for value in values], resource_type)
    except (TypeError, ValueError) as exc:
        raise PlatformValidationError(
            "digital_employee_scope_invalid",
            resource_type,
        ) from exc


def _begin_lifecycle_idempotency(
    uow: Stage06PlatformUnitOfWork,
    *,
    employee: DigitalEmployee,
    actor: Actor,
    operation: str,
    expected_version: int,
    idempotency_key: str,
):
    fingerprint = fingerprint_request(
        {
            "operation": operation,
            "employee_id": str(employee.id),
            "actor_id": actor.actor_id,
            "expected_version": expected_version,
        }
    )
    return begin_idempotent_operation(
        uow,
        workspace_id=employee.workspace_id,
        operation=operation,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        trace_id=idempotency_trace_id(operation, fingerprint, idempotency_key),
    )


def _employee_from_idempotency_replay(
    uow: Stage06PlatformUnitOfWork,
    response_ref: dict[str, object] | None,
    operation: str,
) -> DigitalEmployee:
    employee_id = _response_uuid(response_ref, "employee_id", operation)
    employee = uow.get_digital_employee(employee_id)
    if employee is None:
        raise PlatformValidationError("idempotency_in_progress", operation)
    return employee


def _lifecycle_receipt_from_replay(
    response_ref: dict[str, object] | None,
    operation: str,
) -> ManagedEmployeeLifecycleReceipt:
    return ManagedEmployeeLifecycleReceipt(
        id=_response_uuid(response_ref, "employee_id", operation),
        status=_response_string(response_ref, "status", operation),
        version=_response_integer(response_ref, "version", operation),
        audit_event_id=_response_uuid(response_ref, "audit_event_id", operation),
    )


def _lifecycle_receipt_response(
    receipt: ManagedEmployeeLifecycleReceipt,
) -> dict[str, object]:
    return {
        "employee_id": str(receipt.id),
        "status": receipt.status,
        "version": receipt.version,
        "audit_event_id": str(receipt.audit_event_id),
    }


def _response_uuid(
    response_ref: dict[str, object] | None,
    key: str,
    operation: str,
) -> UUID:
    try:
        return UUID(str((response_ref or {})[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise PlatformValidationError("idempotency_in_progress", operation) from exc


def _response_string(
    response_ref: dict[str, object] | None,
    key: str,
    operation: str,
) -> str:
    value = (response_ref or {}).get(key)
    if not isinstance(value, str):
        raise PlatformValidationError("idempotency_in_progress", operation)
    return value


def _response_integer(
    response_ref: dict[str, object] | None,
    key: str,
    operation: str,
) -> int:
    value = (response_ref or {}).get(key)
    if not isinstance(value, int):
        raise PlatformValidationError("idempotency_in_progress", operation)
    return value


def _record_management_audit(
    uow: Stage06PlatformUnitOfWork,
    *,
    actor: Actor,
    event_type: str,
    employee: DigitalEmployee,
    before_status: str | None,
    member_count: int | None = None,
):
    state = {
        "base_id": str(employee.base_id),
        "employee_id": str(employee.id),
        "status": employee.status,
        "version": employee.version,
        "access_mode": _employee_access_mode(employee),
        "table_count": len(employee.accessible_tables),
        "view_count": len(employee.accessible_views),
        "allowed_actions": list(employee.allowed_actions),
    }
    if before_status is not None:
        state["before"] = {"status": before_status}
    if member_count is not None:
        state["member_count"] = member_count
    event = record_audit_event(
        getattr(uow, "session", uow),
        trace_id=f"stage07:digital-employee-management:{employee.id}:{employee.version}",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        event_type=event_type,
        entity_type="digital_employee",
        entity_id=employee.id,
        after_state=sanitize_stage06_audit_state(state),
        permission_snapshot=sanitize_stage06_audit_state(
            {"actor_type": actor.actor_type, "role": actor.role}
        ),
    )
    if event.id is None:
        event.id = uuid4()
    return event
