from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from app.models.agent_event_runtime import AgentArtifact, AgentPrivateInput
from app.schemas.agent_event_runtime import (
    AgentCommandEnvelope,
    AgentEventEnvelope,
    AgentRunCreateRequest,
)
from app.schemas.agent_task_spec_v2 import (
    ActionSlotV1,
    AuthorizedEntitySpec,
    PlannerRequestV2,
)
from app.schemas.authorized_query_plan import (
    StructuredQueryResultV1,
    structured_query_result_sha256,
)
from app.schemas.stage12_action_runtime import (
    ActionPrivatePayloadV1,
    ActionSlotControlV1,
    DurableAuthorizedCandidateSetV1,
    DurableTaskSpecV2,
    action_candidate_sha256,
)
from app.schemas.agent_specialist_results import specialist_payload_sha256
from app.services.agent_action_candidates import resolve_action_candidates
from app.services.agent_authorized_entity_linker import (
    build_authorized_entity_candidates,
)
from app.services.agent_event_runtime import (
    AgentEventRuntimeUnitOfWork,
    append_agent_runtime_event,
    create_agent_run,
)
from app.services.agent_field_policy_v2 import build_stage12_action_scope_hash
from app.services.agent_orchestrator import (
    SpecialistCommandDispatch,
    dispatch_specialist_commands,
)
from app.services.agent_schema_binding import (
    build_authorized_relation_catalog,
    build_authorized_schema_snapshot,
)
from app.services.agent_task_planner_v2 import plan_task_v2
from app.services.agent_typed_artifacts import persist_typed_artifact
from app.services.authorized_query_compiler import compile_authorized_query_plan
from app.services.authorized_table_query import execute_authorized_query
from app.services.permissions import Actor
from app.services.stage06_platform import Stage06PlatformUnitOfWork, list_view_records
from app.services.stage12_action_private_payload import (
    seal_stage12_action_private_payload,
)
from app.services.stage12_action_runtime import (
    Stage12ActionRuntimeRepository,
    create_action_slot,
    create_objective_run,
    transition_action_slot,
)
from app.workers.stage12_action_runtime import process_stage12_action_command


_ACTION_KIND = {
    "draft_create": "record.create",
    "draft_update": "record.update",
    "task_create": "task.create",
    "reminder_request": "reminder.request",
}
_EMPLOYEE_ACTION_KINDS = {
    "draft_create": ("record.create", "task.create"),
    "draft_update": ("record.update",),
    "notification.request": ("reminder.request",),
}


class Stage12ActionAdmissionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Stage12ActionAdmissionResult:
    run_id: UUID
    status: str
    replayed: bool
    objective_count: int
    action_count: int


def admit_stage12_action_run(
    platform_uow: Stage06PlatformUnitOfWork,
    runtime_uow: AgentEventRuntimeUnitOfWork,
    action_repository: Stage12ActionRuntimeRepository,
    *,
    request: AgentRunCreateRequest,
    actor: Actor,
    private_key_b64: str,
    private_key_version: str,
    embedded: bool,
    now: datetime | None = None,
) -> Stage12ActionAdmissionResult:
    now = now or datetime.now(UTC)
    requested_action_kind = _ACTION_KIND.get(request.requested_action)
    if request.requested_action != "auto" and requested_action_kind is None:
        raise Stage12ActionAdmissionError("stage12_action_request_required")
    snapshot = build_authorized_schema_snapshot(
        platform_uow,
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        actor=actor,
        require_field_policy_v2=True,
    )
    employee = platform_uow.get_digital_employee(request.employee_id)
    if employee is None:
        raise Stage12ActionAdmissionError("action_employee_not_found")
    employee_allowed = set(employee.allowed_actions)
    allowed_action_kinds = tuple(
        dict.fromkeys(
            action_kind
            for employee_action, action_kinds in _EMPLOYEE_ACTION_KINDS.items()
            if employee_action in employee_allowed
            for action_kind in action_kinds
        )
    )
    if requested_action_kind is not None:
        if requested_action_kind not in set(allowed_action_kinds):
            raise Stage12ActionAdmissionError("stage12_action_capability_denied")
        allowed_action_kinds = (requested_action_kind,)
    if not allowed_action_kinds:
        raise Stage12ActionAdmissionError("stage12_action_capability_denied")
    view_ids = tuple(
        sorted((UUID(value) for value in employee.accessible_views), key=str)
    )
    entities = (
        _target_entities(platform_uow, snapshot, request.target_record_id)
        if request.target_record_id is not None
        else build_authorized_entity_candidates(
            platform_uow,
            query=request.query,
            actor=actor,
            workspace_id=request.workspace_id,
            base_id=employee.base_id,
            employee_id=employee.id,
            snapshot=snapshot,
            chat_authorized_view_ids=view_ids or None,
            allow_whole_table=not view_ids,
        )
    )
    artifact = plan_task_v2(
        PlannerRequestV2(
            query=request.query,
            authorized_schema=snapshot,
            authorized_entities=entities,
            clock=now,
            timezone_name="Asia/Shanghai",
            allowed_action_kinds=allowed_action_kinds,
        )
    )
    planned_slots = tuple(
        item
        for item in artifact.task_spec.action_slots
        if item.action_kind in set(allowed_action_kinds)
    )
    if not planned_slots:
        raise Stage12ActionAdmissionError("stage12_action_slot_missing")
    scope_hash = build_stage12_action_scope_hash(
        schema_scope_hash=snapshot.scope_hash,
        target_record_id=request.target_record_id,
    )
    run_key_hash = hashlib.sha256(
        (
            f"stage12-action:{request.workspace_id}:{actor.actor_id}:"
            f"{request.idempotency_key}"
        ).encode("utf-8")
    ).hexdigest()
    creation = create_agent_run(
        runtime_uow,
        workspace_id=request.workspace_id,
        root_employee_id=request.employee_id,
        target_record_id=request.target_record_id,
        scope_hash=scope_hash,
        idempotency_key_hash=run_key_hash,
        deadline_at=now.replace(microsecond=0) + timedelta(seconds=90),
        now=now,
        workflow_version="stage12.quality-v2.action.v1",
    )
    run = creation.run
    if creation.replayed:
        return Stage12ActionAdmissionResult(
            run_id=run.id,
            status=run.status,
            replayed=True,
            objective_count=len(action_repository.list_objectives(run.id)),
            action_count=len(action_repository.list_actions(run.id)),
        )
    _persist_task_spec_artifact(
        platform_uow,
        runtime_uow,
        workspace_id=run.workspace_id,
        run_id=run.id,
        scope_hash=scope_hash,
        artifact=artifact,
        expires_at=run.deadline_at,
    )
    objectives = {
        item.objective_id: create_objective_run(
            action_repository,
            run_id=run.id,
            objective_key=item.objective_id,
            kind=item.kind,
            required=item.required,
            dependency_keys=tuple(
                edge.from_objective_id
                for edge in artifact.task_spec.dependency_edges
                if edge.to_objective_id == item.objective_id
            ),
        )
        for item in artifact.task_spec.objectives
    }
    dispatches: list[SpecialistCommandDispatch] = []
    dispatch_targets: list[tuple[object, UUID]] = []
    logical_slot_counts: dict[str, int] = {}
    for logical_slot in planned_slots:
        logical_slot_counts[logical_slot.objective_id] = (
            logical_slot_counts.get(logical_slot.objective_id, 0) + 1
        )
    logical_slot_indexes: dict[str, int] = {}
    for logical_slot in planned_slots:
        objective = objectives[logical_slot.objective_id]
        if logical_slot_counts[logical_slot.objective_id] > 1:
            logical_index = logical_slot_indexes.get(logical_slot.objective_id, 0) + 1
            logical_slot_indexes[logical_slot.objective_id] = logical_index
            objective = create_objective_run(
                action_repository,
                run_id=run.id,
                objective_key=f"{logical_slot.objective_id}:{logical_index}",
                kind=objective.kind,
                required=objective.required,
                dependency_keys=tuple(objective.dependency_keys),
            )
        if logical_slot.planning_outcome != "planned":
            _persist_denied_slot(
                action_repository,
                run_id=run.id,
                objective=objective,
                logical_slot=logical_slot,
                snapshot=snapshot,
                scope_hash=scope_hash,
            )
            continue
        query_result = _query_result_for_slot(
            platform_uow,
            request=request,
            actor=actor,
            snapshot=snapshot,
            task_spec=artifact.task_spec,
            slot=logical_slot,
            authorized_entities=entities,
        )
        logical_slot, binding_denial = _bind_deferred_create_source(
            platform_uow,
            logical_slot,
            query_result=query_result,
            snapshot=snapshot,
            query=request.query,
            authorized_entities=entities,
        )
        if binding_denial is not None:
            _persist_denied_slot(
                action_repository,
                run_id=run.id,
                objective=objective,
                logical_slot=logical_slot,
                snapshot=snapshot,
                scope_hash=scope_hash,
                reason=binding_denial,
            )
            continue
        resolution = resolve_action_candidates(
            logical_slot,
            snapshot=snapshot,
            query_result=query_result,
        )
        if resolution.status == "denied":
            _persist_denied_slot(
                action_repository,
                run_id=run.id,
                objective=objective,
                logical_slot=logical_slot,
                snapshot=snapshot,
                scope_hash=scope_hash,
                reason=resolution.denial_reason,
            )
            continue
        concrete = resolution.candidates or (None,)
        for index, candidate in enumerate(concrete, start=1):
            concrete_objective = objective
            slot_key = logical_slot.slot_id
            if len(concrete) > 1:
                concrete_objective = create_objective_run(
                    action_repository,
                    run_id=run.id,
                    objective_key=f"{logical_slot.objective_id}:{index}",
                    kind=objective.kind,
                    required=objective.required,
                    dependency_keys=tuple(objective.dependency_keys),
                )
                slot_key = f"{logical_slot.slot_id}:{index}"
            candidate_set = _concrete_candidate_set(
                resolution,
                candidate,
                objective_key=concrete_objective.objective_key,
                slot_key=slot_key,
            )
            control = _action_control(logical_slot, snapshot)
            private_id = uuid4()
            command_id = uuid4()
            reminder_target, reminder_message = _reminder_payload(
                platform_uow,
                snapshot,
                logical_slot,
                None if candidate is None else candidate.record_id,
                request.query,
            )
            if (
                logical_slot.action_kind == "reminder.request"
                and reminder_target is None
            ):
                _persist_denied_slot(
                    action_repository,
                    run_id=run.id,
                    objective=concrete_objective,
                    logical_slot=logical_slot,
                    snapshot=snapshot,
                    scope_hash=scope_hash,
                    slot_key=slot_key,
                    reason="action_recipient_unavailable",
                )
                continue
            payload = _private_payload(
                snapshot=snapshot,
                actor_user_id=actor.actor_id,
                logical_slot=logical_slot,
                objective_key=concrete_objective.objective_key,
                slot_key=slot_key,
                candidate=candidate,
                candidate_set=candidate_set,
                reminder_target=reminder_target,
                reminder_message=reminder_message,
                expires_at=run.deadline_at,
            )
            candidate_artifact_id = _persist_candidate_artifact(
                platform_uow,
                runtime_uow,
                workspace_id=run.workspace_id,
                run_id=run.id,
                scope_hash=scope_hash,
                candidate_set=candidate_set,
                expires_at=run.deadline_at,
            )
            data_version_hash = _data_version_hash(payload)
            slot = create_action_slot(
                action_repository,
                run_id=run.id,
                objective_run_id=concrete_objective.id,
                slot_key=slot_key,
                action_kind=logical_slot.action_kind,
                control=control,
                private_payload_ref=f"agent-private-input:{private_id}",
                target_scope_hash=scope_hash,
                data_version_hash=data_version_hash,
                idempotency_key_hash=hashlib.sha256(
                    f"{run.id}:{slot_key}:{candidate_set.candidate_set_hash}".encode(
                        "utf-8"
                    )
                ).hexdigest(),
            )
            sealed = seal_stage12_action_private_payload(
                payload,
                key_b64=private_key_b64,
                key_version=private_key_version,
                run_id=run.id,
                command_id=command_id,
                scope_hash=scope_hash,
            )
            runtime_uow.add_private_input(
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
            dispatches.append(
                SpecialistCommandDispatch(
                    target_capability="platform.action.propose",
                    payload_ref=slot.private_payload_ref,
                    input_artifact_refs=(candidate_artifact_id,),
                    command_id=command_id,
                )
            )
            dispatch_targets.append((concrete_objective, command_id))
    no_dispatch = not dispatches
    if dispatches:
        commands = dispatch_specialist_commands(
            runtime_uow,
            run_id=run.id,
            dispatches=tuple(dispatches),
            authorization_hash=scope_hash,
            now=now,
        )
        for objective, command in zip(
            (item[0] for item in dispatch_targets), commands, strict=True
        ):
            objective.command_id = command.id
            _append_objective_event(
                runtime_uow,
                run=run,
                objective=objective,
                event_type="objective.queued",
                status="queued",
                safe_summary="受控动作 Objective 已进入队列",
                command_id=command.id,
                now=now,
            )
        if embedded:
            for command in commands:
                outbox = runtime_uow.get_outbox_event_by_event_id(command.id)
                if outbox is None:
                    raise Stage12ActionAdmissionError("action_command_outbox_missing")
                envelope = AgentCommandEnvelope.model_validate_json(
                    json.dumps(outbox.payload_json, ensure_ascii=False)
                )
                process_stage12_action_command(
                    runtime_uow,
                    action_repository,
                    platform_uow,
                    envelope,
                    private_key_b64=private_key_b64,
                    worker_id="embedded-stage12-action-worker",
                    now=now,
                )
    for objective in action_repository.list_objectives(run.id):
        if objective.status == "denied":
            _append_objective_event(
                runtime_uow,
                run=run,
                objective=objective,
                event_type="objective.denied",
                status="denied",
                safe_summary="受控动作 Objective 未获授权",
                command_id=None,
                now=now,
            )
    if no_dispatch:
        append_agent_runtime_event(
            runtime_uow,
            AgentEventEnvelope(
                event_id=uuid4(),
                run_id=run.id,
                command_id=None,
                causation_id=run.id,
                correlation_id=run.id,
                sequence=runtime_uow.next_event_sequence(run.id),
                event_type="run.degraded",
                status="degraded",
                source_role="supervisor",
                safe_summary="受控动作均未获得可执行授权候选",
                metrics={"external_send_count": 0},
                occurred_at=now,
            ),
            authorization_hash=scope_hash,
            update_run_status="degraded",
        )
    return Stage12ActionAdmissionResult(
        run_id=run.id,
        status=run.status,
        replayed=False,
        objective_count=len(action_repository.list_objectives(run.id)),
        action_count=len(action_repository.list_actions(run.id)),
    )


def _query_result_for_slot(
    uow,
    *,
    request,
    actor,
    snapshot,
    task_spec,
    slot,
    authorized_entities,
):
    if (
        slot.action_kind in {"record.create", "task.create"}
        and slot.target.query_spec_ref is None
    ):
        return None
    if request.target_record_id is not None:
        record = uow.get_record(request.target_record_id)
        if record is None:
            raise Stage12ActionAdmissionError("action_target_record_not_found")
        employee = uow.get_digital_employee(request.employee_id)
        if employee is None:
            raise Stage12ActionAdmissionError("action_employee_not_found")
        if employee.accessible_views and not _record_visible_in_employee_views(
            uow,
            record_id=record.id,
            table_id=record.table_id,
            view_ids=tuple(UUID(value) for value in employee.accessible_views),
            actor=actor,
        ):
            raise Stage12ActionAdmissionError("action_target_record_scope_denied")
        return _record_result(snapshot, (record,))
    direct_codes = slot.target.record_codes or slot.target.source_entity_codes
    if direct_codes:
        return _authorized_entity_record_result(
            uow,
            snapshot=snapshot,
            target_table_id=slot.target.table_id,
            record_codes=direct_codes,
            authorized_entities=authorized_entities,
        )
    if slot.target.query_spec_ref is None:
        raise Stage12ActionAdmissionError("action_query_result_required")
    query_intent_id = slot.target.query_spec_ref.removeprefix("query-intent:")
    employee = uow.get_digital_employee(request.employee_id)
    if employee is None:
        raise Stage12ActionAdmissionError("action_employee_not_found")
    view_ids = tuple(UUID(value) for value in employee.accessible_views)
    catalog = build_authorized_relation_catalog(uow, snapshot)
    plan = compile_authorized_query_plan(
        task_spec=task_spec,
        query_intent_id=query_intent_id,
        snapshot=snapshot,
        relations=catalog,
        authorized_view_ids=view_ids,
    )
    return execute_authorized_query(
        uow,
        actor=actor,
        workspace_id=request.workspace_id,
        employee_id=request.employee_id,
        chat_view_ids=view_ids or None,
        snapshot=snapshot,
        plan=plan,
        allow_whole_table=not view_ids,
    ).result


def _bind_deferred_create_source(
    uow,
    slot,
    *,
    query_result,
    snapshot,
    query,
    authorized_entities,
):
    if slot.action_kind not in {"record.create", "task.create"}:
        return slot, None
    needs_query_result = any(
        isinstance(assignment.value, dict)
        and assignment.value.get("selector") == "query_result_table"
        for assignment in slot.assignments
    )
    if needs_query_result and (query_result is None or query_result.truncated):
        return slot, "action_query_result_incomplete"

    selected_record_ids: set[UUID] | None = None
    if re.search(r"最高.{0,8}?风险项", query) is not None:
        risk_fields = {
            field.field_id
            for table in snapshot.tables
            for field in table.fields
            if field.key == "risk_level"
        }
        ranked: list[tuple[int, UUID]] = []
        rank = {"high": 3, "medium": 2, "low": 1}
        for record in query_result.records:
            values = {
                item.field_id: item.value
                for item in record.values
                if item.field_id in risk_fields
            }
            scores = [rank.get(str(value).casefold(), 0) for value in values.values()]
            if scores:
                ranked.append((max(scores), record.record_id))
        if not ranked:
            return slot, "highest_risk_target_unavailable"
        highest = max(score for score, _record_id in ranked)
        selected = {record_id for score, record_id in ranked if score == highest}
        if len(selected) != 1:
            return slot, "ambiguous_highest_risk_target"
        selected_record_ids = selected

    assignments = []
    for assignment in slot.assignments:
        selector = assignment.value
        if isinstance(selector, dict) and selector.get("selector") == "project_owner":
            owner_ids, denial = _resolve_project_owner_assignment(
                uow,
                assignment=assignment,
                selector=selector,
                snapshot=snapshot,
                authorized_entities=authorized_entities,
            )
            if denial is not None:
                return slot, denial
            assignments.append(
                assignment.model_copy(
                    update={"value": [str(record_id) for record_id in owner_ids]}
                )
            )
            continue
        if not (
            isinstance(selector, dict)
            and selector.get("selector") == "query_result_table"
            and isinstance(selector.get("source_table_id"), str)
        ):
            linked_value, denial = _resolve_linked_assignment_value(
                uow,
                assignment=assignment,
                snapshot=snapshot,
                authorized_entities=authorized_entities,
                query_result=query_result,
            )
            if denial is not None:
                return slot, denial
            assignments.append(
                assignment
                if linked_value is None
                else assignment.model_copy(update={"value": linked_value})
            )
            continue
        try:
            source_table_id = UUID(selector["source_table_id"])
        except ValueError:
            return slot, "action_source_selector_invalid"
        record_ids = tuple(
            record.record_id
            for record in query_result.records
            if record.table_id == source_table_id
            and (selected_record_ids is None or record.record_id in selected_record_ids)
        )
        if not record_ids:
            return slot, "action_source_candidate_empty"
        assignments.append(
            assignment.model_copy(
                update={"value": [str(record_id) for record_id in record_ids]}
            )
        )
    return slot.model_copy(update={"assignments": tuple(assignments)}), None


def _resolve_linked_assignment_value(
    uow,
    *,
    assignment,
    snapshot,
    authorized_entities,
    query_result,
):
    field = next(
        (
            item
            for table in snapshot.tables
            for item in table.fields
            if item.field_id == assignment.field_id
        ),
        None,
    )
    if field is None or field.field_type != "linked_record":
        return None, None
    if field.linked_target_table_id is None:
        return None, "action_source_selector_invalid"
    raw_values = (
        assignment.value if isinstance(assignment.value, list) else [assignment.value]
    )
    if not raw_values or any(not isinstance(value, str) for value in raw_values):
        return None, "action_source_selector_invalid"
    authorized_by_id = {
        entity.entity_id: entity
        for entity in authorized_entities
        if entity.table_id == field.linked_target_table_id
    }
    authorized_by_code: dict[str, list[object]] = {}
    for entity in authorized_by_id.values():
        authorized_by_code.setdefault(entity.code, []).append(entity)
    query_ids = {
        record.record_id
        for record in (() if query_result is None else query_result.records)
        if record.table_id == field.linked_target_table_id
    }
    resolved: list[str] = []
    for raw_value in raw_values:
        matches = authorized_by_code.get(raw_value, [])
        if len(matches) == 1:
            record_id = matches[0].entity_id
        elif len(matches) > 1:
            return None, "action_source_scope_denied"
        else:
            try:
                record_id = UUID(raw_value)
            except ValueError:
                return None, "action_source_scope_denied"
            if record_id not in authorized_by_id and record_id not in query_ids:
                return None, "action_source_scope_denied"
        record = uow.get_record(record_id)
        if record is None or record.table_id != field.linked_target_table_id:
            return None, "action_source_scope_denied"
        rendered = str(record_id)
        if rendered not in resolved:
            resolved.append(rendered)
    return resolved, None


def _resolve_project_owner_assignment(
    uow,
    *,
    assignment,
    selector,
    snapshot,
    authorized_entities,
):
    raw_codes = selector.get("source_entity_codes")
    if (
        assignment.field_id is None
        or not isinstance(raw_codes, list)
        or not raw_codes
        or any(not isinstance(code, str) or not code.strip() for code in raw_codes)
    ):
        return (), "action_source_selector_invalid"
    codes = tuple(dict.fromkeys(code.strip() for code in raw_codes))
    assignment_field = next(
        (
            field
            for table in snapshot.tables
            for field in table.fields
            if field.field_id == assignment.field_id
        ),
        None,
    )
    if (
        assignment_field is None
        or assignment_field.field_type != "linked_record"
        or assignment_field.linked_target_table_id is None
    ):
        return (), "action_source_selector_invalid"
    matches = {
        code: tuple(entity for entity in authorized_entities if entity.code == code)
        for code in codes
    }
    if any(len(matches[code]) != 1 for code in codes):
        return (), "action_source_scope_denied"

    owner_ids: list[UUID] = []
    for code in codes:
        project = matches[code][0]
        project_table = next(
            (table for table in snapshot.tables if table.table_id == project.table_id),
            None,
        )
        owner_link = next(
            (
                field
                for field in (() if project_table is None else project_table.fields)
                if field.key == "owner_link"
                and field.field_type == "linked_record"
                and field.linked_target_table_id
                == assignment_field.linked_target_table_id
            ),
            None,
        )
        record = uow.get_record(project.entity_id)
        if record is None or owner_link is None or record.table_id != project.table_id:
            return (), "action_project_owner_unavailable"
        raw_owner_ids = record.values.get(owner_link.key)
        if not isinstance(raw_owner_ids, list) or not raw_owner_ids:
            return (), "action_project_owner_unavailable"
        for raw_owner_id in raw_owner_ids:
            try:
                owner_id = UUID(str(raw_owner_id))
            except (TypeError, ValueError, AttributeError):
                return (), "action_project_owner_unavailable"
            owner = uow.get_record(owner_id)
            if (
                owner is None
                or owner.table_id != assignment_field.linked_target_table_id
            ):
                return (), "action_project_owner_unavailable"
            if owner_id not in owner_ids:
                owner_ids.append(owner_id)
    if not owner_ids:
        return (), "action_project_owner_unavailable"
    return tuple(owner_ids), None


def _record_visible_in_employee_views(
    uow,
    *,
    record_id,
    table_id,
    view_ids,
    actor,
):
    matching_views = tuple(
        view_id
        for view_id in view_ids
        if (view := uow.get_view(view_id)) is not None and view.table_id == table_id
    )
    for view_id in matching_views:
        cursor = None
        while True:
            page = list_view_records(
                uow,
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


def _authorized_entity_record_result(
    uow,
    *,
    snapshot,
    target_table_id,
    record_codes,
    authorized_entities,
):
    matches = {}
    for entity in authorized_entities:
        if entity.code not in set(record_codes):
            continue
        if target_table_id is not None and entity.table_id != target_table_id:
            continue
        if entity.code in matches:
            raise Stage12ActionAdmissionError("action_target_record_ambiguous")
        matches[entity.code] = entity
    if set(matches) != set(record_codes):
        raise Stage12ActionAdmissionError("action_target_record_scope_denied")
    records = []
    for code in record_codes:
        entity = matches[code]
        record = uow.get_record(entity.entity_id)
        if record is None or record.table_id != entity.table_id:
            raise Stage12ActionAdmissionError("action_target_record_not_found")
        records.append(record)
    return _record_result(snapshot, tuple(records))


def _record_result(snapshot, records):
    table_ids = {item.table_id for item in snapshot.tables}
    if not records or any(record.table_id not in table_ids for record in records):
        raise Stage12ActionAdmissionError("action_target_record_scope_denied")
    ordered = tuple(dict.fromkeys(record.id for record in records))
    by_id = {record.id: record for record in records}
    values = {
        "version": "structured-query-result.v1",
        "query_plan_version": "authorized-query-plan.v1",
        "plan_hash": hashlib.sha256(
            ("explicit:" + ",".join(str(record_id) for record_id in ordered)).encode()
        ).hexdigest(),
        "records": tuple(
            {
                "record_id": record_id,
                "table_id": by_id[record_id].table_id,
                "values": (),
            }
            for record_id in ordered
        ),
        "groups": (),
        "aggregates": (),
        "relation_paths": (),
        "source_versions": tuple(
            {
                "table_id": by_id[record_id].table_id,
                "record_id": record_id,
                "record_version": by_id[record_id].version,
            }
            for record_id in ordered
        ),
        "scope_hash": snapshot.scope_hash,
        "schema_hash": snapshot.schema_hash,
        "scanned_record_count": len(ordered),
        "traversed_edge_count": 0,
        "truncated": False,
    }
    values["result_hash"] = structured_query_result_sha256(_json_ready(values))
    return StructuredQueryResultV1.model_validate(values)


def _target_entities(uow, snapshot, target_record_id):
    if target_record_id is None:
        return ()
    record = uow.get_record(target_record_id)
    table = next(
        (
            item
            for item in snapshot.tables
            if record is not None and item.table_id == record.table_id
        ),
        None,
    )
    if record is None or table is None:
        raise Stage12ActionAdmissionError("action_target_record_scope_denied")
    field = next(
        (item for item in table.fields if item.field_id == table.identity_field_id),
        None,
    )
    code = str(record.id)
    if field is not None:
        raw = record.values.get(field.key)
        if isinstance(raw, (str, int)) and str(raw).strip():
            code = str(raw).strip()
    return (
        AuthorizedEntitySpec(
            entity_id=record.id,
            table_id=record.table_id,
            code=code,
            label=code,
            aliases=(),
        ),
    )


def _action_control(slot, snapshot):
    fields = {item.field_id: item for table in snapshot.tables for item in table.fields}
    editable = tuple(
        {
            "field_id": assignment.field_id,
            "field_key": assignment.field_key,
            "label": fields[assignment.field_id].name,
            "field_type": fields[assignment.field_id].field_type,
            "required": assignment.field_key in set(slot.required_field_keys),
        }
        for assignment in slot.assignments
        if assignment.field_id in fields and fields[assignment.field_id].writable
    )
    return ActionSlotControlV1(
        action_kind=slot.action_kind,
        confirmation_policy="required",
        dependency_keys=(),
        evidence_refs=(
            (slot.target.query_spec_ref,) if slot.target.query_spec_ref else ()
        ),
        editable_fields=editable,
        safe_summary={
            "record.create": "创建记录草稿，等待确认",
            "record.update": "更新记录草稿，等待确认",
            "task.create": "创建任务草稿，等待确认",
            "reminder.request": "创建提醒请求，等待确认",
        }[slot.action_kind],
    )


def _private_payload(
    *,
    snapshot,
    actor_user_id,
    logical_slot,
    objective_key,
    slot_key,
    candidate,
    candidate_set,
    reminder_target,
    reminder_message,
    expires_at,
):
    record_id = None if candidate is None else candidate.record_id
    return ActionPrivatePayloadV1(
        actor_user_id=actor_user_id,
        objective_key=objective_key,
        slot_key=slot_key,
        action_kind=logical_slot.action_kind,
        field_policy_version=snapshot.field_policy_version,
        field_policy_hash=snapshot.field_policy_hash,
        candidate_set_hash=candidate_set.candidate_set_hash,
        target_table_id=candidate_set.target_table_ids[0],
        target_record_ids=() if record_id is None else (record_id,),
        assignments=tuple(
            {
                "record_id": record_id,
                "field_id": item.field_id,
                "value": item.value,
            }
            for item in logical_slot.assignments
            if item.field_id is not None
        ),
        record_versions=(
            ()
            if candidate is None
            else (
                {
                    "table_id": candidate.table_id,
                    "record_id": candidate.record_id,
                    "record_version": candidate.record_version,
                },
            )
        ),
        evidence_ids=(
            (logical_slot.target.query_spec_ref,)
            if logical_slot.target.query_spec_ref
            else ()
        ),
        reminder_target=reminder_target,
        reminder_message_payload=reminder_message,
        expires_at=expires_at,
    )


def _concrete_candidate_set(
    resolution,
    candidate,
    *,
    objective_key,
    slot_key,
):
    values = resolution.model_dump(mode="json", exclude={"candidate_set_hash"})
    values["objective_key"] = objective_key
    values["slot_key"] = slot_key
    values["candidates"] = (
        [] if candidate is None else [candidate.model_dump(mode="json")]
    )
    values["candidate_set_hash"] = action_candidate_sha256(values)
    return DurableAuthorizedCandidateSetV1.model_validate_json(
        json.dumps(values, ensure_ascii=False)
    )


def _persist_candidate_artifact(
    platform_uow,
    runtime_uow,
    *,
    workspace_id,
    run_id,
    scope_hash,
    candidate_set,
    expires_at,
):
    owner = persist_typed_artifact(
        platform_uow,
        workspace_id=workspace_id,
        run_id=run_id,
        artifact_kind="authorized_candidate_set",
        payload=candidate_set,
        scope_hash=scope_hash,
    )
    artifact_id = uuid4()
    runtime_uow.add_artifact(
        AgentArtifact(
            id=artifact_id,
            run_id=run_id,
            kind="authorized_candidate_set",
            storage_ref=owner.storage_ref,
            content_hash=owner.content_hash,
            visibility_scope_hash=scope_hash,
            validation_status="validated",
            expires_at=expires_at,
        )
    )
    return artifact_id


def _persist_task_spec_artifact(
    platform_uow,
    runtime_uow,
    *,
    workspace_id,
    run_id,
    scope_hash,
    artifact,
    expires_at,
):
    values = {
        "version": "stage12-task-spec-owner.v1",
        "task_spec": artifact.task_spec,
    }
    payload = DurableTaskSpecV2(
        **values,
        content_hash=specialist_payload_sha256(
            {
                "version": values["version"],
                "task_spec": artifact.task_spec.model_dump(mode="json"),
            }
        ),
    )
    owner = persist_typed_artifact(
        platform_uow,
        workspace_id=workspace_id,
        run_id=run_id,
        artifact_kind="task_spec_v2",
        payload=payload,
        scope_hash=scope_hash,
    )
    runtime_uow.add_artifact(
        AgentArtifact(
            id=uuid4(),
            run_id=run_id,
            kind="task_spec_v2",
            storage_ref=owner.storage_ref,
            content_hash=owner.content_hash,
            visibility_scope_hash=scope_hash,
            validation_status="validated",
            expires_at=expires_at,
        )
    )


def _persist_denied_slot(
    repository,
    *,
    run_id,
    objective,
    logical_slot,
    snapshot,
    scope_hash,
    slot_key=None,
    reason=None,
):
    key = slot_key or logical_slot.slot_id
    control = _action_control(logical_slot, snapshot).model_copy(
        update={"safe_summary": "动作未获授权，未生成草稿"}
    )
    slot = create_action_slot(
        repository,
        run_id=run_id,
        objective_run_id=objective.id,
        slot_key=key,
        action_kind=logical_slot.action_kind,
        control=control,
        private_payload_ref=f"denied:{uuid4()}",
        target_scope_hash=scope_hash,
        data_version_hash=None,
        idempotency_key_hash=hashlib.sha256(
            f"{run_id}:{key}:denied:{reason or logical_slot.denial_reason}".encode()
        ).hexdigest(),
    )
    transition_action_slot(
        repository,
        slot_id=slot.id,
        expected_proposal_version=slot.proposal_version,
        target_status="denied",
    )
    objective.status = "denied"
    objective.error_code = reason or logical_slot.denial_reason or "action_denied"


def _reminder_payload(uow, snapshot, slot, record_id, query):
    if slot.action_kind != "reminder.request":
        return None, None
    if record_id is None:
        return None, None
    record = uow.get_record(record_id)
    table = next(
        (
            item
            for item in snapshot.tables
            if record is not None and item.table_id == record.table_id
        ),
        None,
    )
    if record is None or table is None:
        return None, None
    for key in (
        "telegram_chat_id",
        "assignee_chat_id",
        "owner_chat_id",
        "owner",
        "assignee",
    ):
        if not any(item.key == key for item in table.fields):
            continue
        raw = record.values.get(key)
        if isinstance(raw, dict):
            raw = raw.get("telegram_chat_id")
        if isinstance(raw, (str, int)) and str(raw).strip():
            return {"telegram_chat_id": str(raw).strip()}, {"text": query}
    return None, None


def _data_version_hash(payload):
    if not payload.record_versions:
        return None
    return hashlib.sha256(
        json.dumps(
            [item.model_dump(mode="json") for item in payload.record_versions],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _json_ready(value):
    return TypeAdapter(dict[str, object]).dump_python(value, mode="json")


def _append_objective_event(
    runtime_uow,
    *,
    run,
    objective,
    event_type,
    status,
    safe_summary,
    command_id,
    now,
):
    append_agent_runtime_event(
        runtime_uow,
        AgentEventEnvelope(
            event_id=uuid4(),
            run_id=run.id,
            command_id=command_id,
            causation_id=objective.id,
            correlation_id=run.id,
            sequence=runtime_uow.next_event_sequence(run.id),
            event_type=event_type,
            status=(
                status
                if status in {"queued", "running", "completed", "degraded"}
                else "degraded"
            ),
            source_role="supervisor",
            source_capability=None,
            safe_summary=safe_summary,
            metrics={},
            occurred_at=now,
        ),
        authorization_hash=run.scope_hash,
    )


__all__ = [
    "Stage12ActionAdmissionError",
    "Stage12ActionAdmissionResult",
    "admit_stage12_action_run",
]
