from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import get_stage06_request_identity
from app.api.routes.agent_runs import (
    get_agent_event_runtime_uow,
    get_stage12_action_repository,
)
from app.api.routes.stage06_platform import get_stage06_platform_uow
from app.core.config import Settings, durable_action_v1_enabled, get_settings
from app.core.errors import error_detail
from app.schemas.stage12_action_runtime import (
    ActionConfirmRequestV1,
    ActionRejectRequestV1,
    ActionTerminalReceiptV1,
    ActionSlotControlV1,
    SafeActionListV1,
    SafeActionSlotV1,
    SafeEvidenceV1,
    SafeObjectiveListV1,
    SafeObjectiveRunV1,
)
from app.services.agent_event_runtime import (
    AgentEventRuntimeUnitOfWork,
    RuntimeNotFound,
)
from app.services.agent_field_policy_v2 import build_stage12_action_scope_hash
from app.services.agent_orchestrator import build_authorization_hash
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.stage06_authorization import (
    Stage06AuthorizationError,
    authorize_workspace_action,
)
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_identity import Stage06RequestIdentity
from app.services.stage06_platform import (
    PlatformValidationError,
    Stage06PlatformUnitOfWork,
    list_view_records,
)
from app.services.stage12_action_confirmation import (
    confirm_stage12_action,
    reject_stage12_action,
)
from app.services.stage12_action_private_payload import (
    Stage12ActionPrivatePayloadError,
    open_stage12_action_private_payload,
)
from app.services.stage12_action_runtime import (
    Stage12ActionConflict,
    Stage12ActionNotFound,
    Stage12ActionRuntimeRepository,
)


router = APIRouter(prefix="/api/stage10/agent-runs", tags=["stage12-actions"])

_ACTION_REQUIRED_EMPLOYEE_ACTION = {
    "record.create": "draft_create",
    "record.update": "draft_update",
    "task.create": "draft_create",
    "reminder.request": "notification.request",
}


@router.get("/{run_id}/objectives", response_model=SafeObjectiveListV1)
def list_agent_objectives(
    run_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    settings: Settings = Depends(get_settings),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
    actions: Stage12ActionRuntimeRepository = Depends(get_stage12_action_repository),
) -> SafeObjectiveListV1:
    run, _actor = _authorize_run(run_id, identity, settings, platform_uow, runtime_uow)
    return SafeObjectiveListV1(
        run_id=run.id,
        objectives=tuple(
            SafeObjectiveRunV1(
                objective_id=item.id,
                objective_key=item.objective_key,
                kind=item.kind,
                required=item.required,
                status=item.status,
                safe_summary=_objective_summary(item),
                error_code=item.error_code,
            )
            for item in actions.list_objectives(run.id)
        ),
    )


@router.get("/{run_id}/actions", response_model=SafeActionListV1)
def list_agent_actions(
    run_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    settings: Settings = Depends(get_settings),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
    actions: Stage12ActionRuntimeRepository = Depends(get_stage12_action_repository),
) -> SafeActionListV1:
    run, actor = _authorize_run(run_id, identity, settings, platform_uow, runtime_uow)
    slots = tuple(actions.list_actions(run.id))
    for slot in slots:
        payload = (
            _open_action_payload(slot, runtime_uow, settings)
            if slot.private_payload_ref.startswith("agent-private-input:")
            else None
        )
        _authorize_current_action_scope(
            platform_uow,
            run=run,
            slot=slot,
            payload=payload,
            actor=actor,
        )
    return SafeActionListV1(
        run_id=run.id,
        actions=tuple(_safe_action(item, runtime_uow, settings) for item in slots),
    )


@router.get("/{run_id}/evidence/{evidence_id}", response_model=SafeEvidenceV1)
def get_agent_evidence(
    run_id: UUID,
    evidence_id: UUID,
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    settings: Settings = Depends(get_settings),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
) -> SafeEvidenceV1:
    run, _actor = _authorize_run(run_id, identity, settings, platform_uow, runtime_uow)
    artifact = runtime_uow.get_artifact(evidence_id)
    if (
        artifact is None
        or artifact.run_id != run.id
        or artifact.visibility_scope_hash != run.scope_hash
    ):
        raise HTTPException(
            status_code=404,
            detail=error_detail("agent_evidence_not_found", "agent_evidence_not_found"),
        )
    summary = next(
        (
            item.safe_summary
            for item in runtime_uow.list_events(run.id)
            if item.artifact_ref == artifact.id and item.safe_summary
        ),
        None,
    )
    return SafeEvidenceV1(
        evidence_id=artifact.id,
        kind=artifact.kind,
        validation_status=artifact.validation_status,
        safe_summary=summary,
    )


@router.post(
    "/{run_id}/actions/{slot_id}/confirm",
    response_model=ActionTerminalReceiptV1,
)
def confirm_agent_action(
    run_id: UUID,
    slot_id: UUID,
    request: ActionConfirmRequestV1,
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=1, max_length=160
    ),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    settings: Settings = Depends(get_settings),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
    actions: Stage12ActionRuntimeRepository = Depends(get_stage12_action_repository),
) -> ActionTerminalReceiptV1:
    run, actor = _authorize_run(run_id, identity, settings, platform_uow, runtime_uow)
    if not durable_action_v1_enabled(settings, run.workspace_id):
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "durable_action_runtime_disabled",
                "durable_action_runtime_disabled",
            ),
        )
    slot = _require_slot(actions, run.id, slot_id)
    _authorize_terminal_action(platform_uow, identity, run.workspace_id, slot)
    payload = _open_action_payload(slot, runtime_uow, settings)
    _authorize_current_action_scope(
        platform_uow,
        run=run,
        slot=slot,
        payload=payload,
        actor=actor,
    )
    fingerprint = fingerprint_request(
        {
            "run_id": str(run.id),
            "slot_id": str(slot.id),
            "request": request.model_dump(mode="json"),
            "user_id": identity.user_id,
        }
    )
    try:
        decision = begin_idempotent_operation(
            platform_uow,
            workspace_id=run.workspace_id,
            operation="stage12.action.confirm",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            trace_id=idempotency_trace_id(
                "stage12.action.confirm", fingerprint, idempotency_key
            ),
        )
        if decision.status == "replay":
            return _receipt(slot, replayed=True)
        receipt = confirm_stage12_action(
            actions,
            runtime_uow,
            platform_uow,
            run_id=run.id,
            slot_id=slot.id,
            request=request,
            private_payload=payload,
            actor=actor,
        )
        complete_idempotent_operation(
            decision.record,
            response_ref={"slot_id": str(slot.id), "status": receipt.status},
        )
        _commit(runtime_uow)
        return receipt
    except (Stage12ActionConflict, PlatformValidationError) as exc:
        _rollback(runtime_uow)
        raise _action_http_error(exc) from exc


@router.post(
    "/{run_id}/actions/{slot_id}/reject",
    response_model=ActionTerminalReceiptV1,
)
def reject_agent_action(
    run_id: UUID,
    slot_id: UUID,
    request: ActionRejectRequestV1,
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=1, max_length=160
    ),
    identity: Stage06RequestIdentity = Depends(get_stage06_request_identity),
    settings: Settings = Depends(get_settings),
    platform_uow: Stage06PlatformUnitOfWork = Depends(get_stage06_platform_uow),
    runtime_uow: AgentEventRuntimeUnitOfWork = Depends(get_agent_event_runtime_uow),
    actions: Stage12ActionRuntimeRepository = Depends(get_stage12_action_repository),
) -> ActionTerminalReceiptV1:
    run, actor = _authorize_run(run_id, identity, settings, platform_uow, runtime_uow)
    slot = _require_slot(actions, run.id, slot_id)
    _authorize_terminal_action(
        platform_uow, identity, run.workspace_id, slot, reject=True
    )
    payload = _open_action_payload(slot, runtime_uow, settings)
    _authorize_current_action_scope(
        platform_uow,
        run=run,
        slot=slot,
        payload=payload,
        actor=actor,
    )
    fingerprint = fingerprint_request(
        {
            "run_id": str(run.id),
            "slot_id": str(slot.id),
            "request": request.model_dump(mode="json"),
            "user_id": identity.user_id,
        }
    )
    try:
        decision = begin_idempotent_operation(
            platform_uow,
            workspace_id=run.workspace_id,
            operation="stage12.action.reject",
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            trace_id=idempotency_trace_id(
                "stage12.action.reject", fingerprint, idempotency_key
            ),
        )
        if decision.status == "replay":
            return _receipt(slot, replayed=True)
        receipt = reject_stage12_action(
            actions,
            runtime_uow,
            platform_uow,
            run_id=run.id,
            slot_id=slot.id,
            request=request,
            actor=actor,
        )
        complete_idempotent_operation(
            decision.record,
            response_ref={"slot_id": str(slot.id), "status": receipt.status},
        )
        _commit(runtime_uow)
        return receipt
    except (Stage12ActionConflict, PlatformValidationError) as exc:
        _rollback(runtime_uow)
        raise _action_http_error(exc) from exc


def _authorize_run(run_id, identity, settings, platform_uow, runtime_uow):
    if not settings.agent_event_runtime_enabled:
        raise HTTPException(
            status_code=404,
            detail=error_detail(
                "agent_event_runtime_disabled", "agent_event_runtime_disabled"
            ),
        )
    run = runtime_uow.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=error_detail("agent_run_not_found", "agent_run_not_found"),
        )
    if (
        settings.agent_event_runtime_allowed_workspace_ids
        and str(run.workspace_id)
        not in settings.agent_event_runtime_allowed_workspace_ids
    ):
        raise HTTPException(
            status_code=404,
            detail=error_detail(
                "agent_event_runtime_disabled", "agent_event_runtime_disabled"
            ),
        )
    try:
        actor = authorize_workspace_action(
            platform_uow, identity, run.workspace_id, "digital_employee.invoke"
        )
    except Stage06AuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail=error_detail("action_scope_changed", "action_scope_changed"),
        ) from exc
    try:
        if run.workflow_version == "stage12.quality-v2.action.v1":
            snapshot = build_authorized_schema_snapshot(
                platform_uow,
                workspace_id=run.workspace_id,
                employee_id=run.root_employee_id,
                actor=actor,
                require_field_policy_v2=True,
            )
            current = build_stage12_action_scope_hash(
                schema_scope_hash=snapshot.scope_hash,
                target_record_id=run.target_record_id,
            )
        else:
            current = build_authorization_hash(
                workspace_id=run.workspace_id,
                employee_id=run.root_employee_id,
                target_record_id=run.target_record_id,
                actor_user_id=actor.actor_id,
            )
    except (PlatformValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=403,
            detail=error_detail("action_scope_changed", "action_scope_changed"),
        ) from exc
    if current != run.scope_hash:
        raise HTTPException(
            status_code=403,
            detail=error_detail("action_scope_changed", "action_scope_changed"),
        )
    return run, actor


def _authorize_terminal_action(
    platform_uow, identity, workspace_id, slot, *, reject=False
):
    operation = (
        "notification_request.confirm"
        if slot.action_kind == "reminder.request"
        else "record_change_draft.reject" if reject else "record_change_draft.confirm"
    )
    try:
        authorize_workspace_action(
            platform_uow,
            identity,
            workspace_id,
            operation,
        )
    except Stage06AuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail=error_detail("action_scope_changed", "action_scope_changed"),
        ) from exc


def _authorize_current_action_scope(
    platform_uow,
    *,
    run,
    slot,
    payload,
    actor,
):
    employee = platform_uow.get_digital_employee(run.root_employee_id)
    required_action = _ACTION_REQUIRED_EMPLOYEE_ACTION.get(slot.action_kind)
    if (
        employee is None
        or employee.status != "active"
        or employee.workspace_id != run.workspace_id
        or required_action is None
        or required_action not in set(employee.allowed_actions)
    ):
        _scope_changed()
    try:
        snapshot = build_authorized_schema_snapshot(
            platform_uow,
            workspace_id=run.workspace_id,
            employee_id=run.root_employee_id,
            actor=actor,
            require_field_policy_v2=(
                run.workflow_version == "stage12.quality-v2.action.v1"
            ),
        )
    except PlatformValidationError:
        _scope_changed()
    if payload is None:
        return
    if run.workflow_version == "stage12.quality-v2.action.v1" and (
        payload.field_policy_version != snapshot.field_policy_version
        or payload.field_policy_hash != snapshot.field_policy_hash
    ):
        _scope_changed()
    tables = {item.table_id: item for item in snapshot.tables}
    table = tables.get(payload.target_table_id)
    if table is None:
        _scope_changed()
    writable_fields = {item.field_id for item in table.fields if item.writable}
    control = ActionSlotControlV1.model_validate_json(
        json.dumps(slot.control_json, ensure_ascii=False, separators=(",", ":"))
    )
    authorized_field_ids = {item.field_id for item in control.editable_fields}
    if not authorized_field_ids.issubset(writable_fields) or any(
        item.field_id not in writable_fields for item in payload.assignments
    ):
        _scope_changed()
    for record_id in payload.target_record_ids:
        record = platform_uow.get_record(record_id)
        if record is None or record.table_id != payload.target_table_id:
            _scope_changed()
        if employee.accessible_views and not _record_visible_in_current_views(
            platform_uow,
            record_id=record_id,
            table_id=record.table_id,
            view_ids=employee.accessible_views,
            actor=actor,
        ):
            _scope_changed()


def _record_visible_in_current_views(
    platform_uow,
    *,
    record_id,
    table_id,
    view_ids,
    actor,
):
    try:
        parsed_view_ids = tuple(UUID(str(value)) for value in view_ids)
    except ValueError:
        _scope_changed()
    matching = tuple(
        view_id
        for view_id in parsed_view_ids
        if (view := platform_uow.get_view(view_id)) is not None
        and view.table_id == table_id
    )
    for view_id in matching:
        cursor = None
        while True:
            page = list_view_records(
                platform_uow,
                view_id,
                actor=actor,
                limit=200,
                cursor=cursor,
            )
            if any(str(item.get("id")) == str(record_id) for item in page["records"]):
                return True
            if not page.get("has_more"):
                break
            cursor = page.get("next_cursor")
            if not isinstance(cursor, str) or not cursor:
                break
    return False


def _scope_changed():
    raise HTTPException(
        status_code=403,
        detail=error_detail("action_scope_changed", "action_scope_changed"),
    )


def _require_slot(actions, run_id, slot_id):
    slot = actions.get_action(slot_id, for_update=True)
    if slot is None or slot.run_id != run_id:
        raise HTTPException(
            status_code=404,
            detail=error_detail("action_slot_not_found", "action_slot_not_found"),
        )
    return slot


def _open_action_payload(slot, runtime_uow, settings):
    prefix = "agent-private-input:"
    if (
        settings.agent_runtime_input_key is None
        or not slot.private_payload_ref.startswith(prefix)
    ):
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "action_private_payload_unavailable",
                "action_private_payload_unavailable",
            ),
        )
    try:
        private_id = UUID(slot.private_payload_ref.removeprefix(prefix))
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "action_private_payload_unavailable",
                "action_private_payload_unavailable",
            ),
        ) from exc
    sealed = runtime_uow.get_private_input(private_id)
    if sealed is None:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "action_private_payload_unavailable",
                "action_private_payload_unavailable",
            ),
        )
    try:
        from datetime import UTC, datetime

        return open_stage12_action_private_payload(
            sealed,
            key_b64=settings.agent_runtime_input_key,
            run_id=slot.run_id,
            command_id=sealed.command_id,
            scope_hash=slot.target_scope_hash,
            now=datetime.now(UTC),
        )
    except Stage12ActionPrivatePayloadError as exc:
        raise HTTPException(
            status_code=409, detail=error_detail(str(exc), str(exc))
        ) from exc


def _safe_action(slot, runtime_uow, settings):
    control = ActionSlotControlV1.model_validate_json(json.dumps(slot.control_json))
    proposed = {}
    record_version = None
    if slot.private_payload_ref.startswith("agent-private-input:"):
        payload = _open_action_payload(slot, runtime_uow, settings)
        keys = {item.field_id: item.field_key for item in control.editable_fields}
        proposed = {
            keys[item.field_id]: item.value
            for item in payload.assignments
            if item.field_id in keys
        }
        if slot.action_kind == "record.update" and len(payload.record_versions) == 1:
            record_version = payload.record_versions[0].record_version
    return SafeActionSlotV1(
        slot_id=slot.id,
        objective_id=slot.objective_run_id,
        slot_key=slot.slot_key,
        action_kind=slot.action_kind,
        status=slot.status,
        proposal_version=slot.proposal_version,
        record_version=record_version,
        safe_summary=control.safe_summary,
        editable_fields=control.editable_fields,
        proposed_values=proposed,
        execution_ticket_id=slot.execution_ticket_id,
        resource_id=slot.materialized_resource_id,
    )


def _objective_summary(value):
    return None if value.error_code else f"{value.kind}：{value.status}"


def _receipt(slot, *, replayed):
    return ActionTerminalReceiptV1(
        slot_id=slot.id,
        status=slot.status,
        proposal_version=slot.proposal_version,
        execution_ticket_id=slot.execution_ticket_id,
        resource_id=slot.materialized_resource_id,
        replayed=replayed,
    )


def _action_http_error(exc):
    code = getattr(exc, "code", str(exc))
    if (
        code in {"action_scope_changed", "action_field_scope_changed"}
        or "permission" in code
    ):
        status_code = 403
        code = "action_scope_changed"
    elif code.endswith("_not_found"):
        status_code = 404
    else:
        status_code = 409
    return HTTPException(status_code=status_code, detail=error_detail(code, code))


def _commit(uow):
    session = getattr(uow, "session", None)
    if session is not None:
        session.commit()


def _rollback(uow):
    session = getattr(uow, "session", None)
    if session is not None:
        session.rollback()


__all__ = ["get_stage12_action_repository", "router"]
