from __future__ import annotations

from app.schemas.agent_task_spec_v2 import (
    ActionSlotV1,
    AuthorizedSchemaSnapshot,
)
from app.schemas.authorized_query_plan import StructuredQueryResultV1
from app.schemas.stage12_action_runtime import (
    DurableAuthorizedCandidateSetV1,
    action_candidate_sha256,
)


_CREATE_ACTIONS = frozenset({"record.create", "task.create"})


def resolve_action_candidates(
    slot: ActionSlotV1,
    *,
    snapshot: AuthorizedSchemaSnapshot,
    query_result: StructuredQueryResultV1 | None,
) -> DurableAuthorizedCandidateSetV1:
    if slot.planning_outcome != "planned":
        return _denied(slot, snapshot, query_result, "action_slot_not_planned")
    table = _resolve_table(slot, snapshot, query_result)
    if table is None:
        return _denied(slot, snapshot, query_result, "action_target_table_unavailable")
    fields = {item.field_id: item for item in table.fields}
    assignment_ids = tuple(
        item.field_id for item in slot.assignments if item.field_id is not None
    )
    if len(assignment_ids) != len(slot.assignments) or any(
        field_id not in fields or not fields[field_id].writable
        for field_id in assignment_ids
    ):
        return _denied(slot, snapshot, query_result, "action_field_not_writable")
    assigned_keys = {item.field_key for item in slot.assignments}
    fields_by_key = {item.key: item for item in table.fields}
    if any(
        key not in assigned_keys
        and (key not in fields_by_key or fields_by_key[key].default_value is None)
        for key in slot.required_field_keys
    ):
        return _denied(slot, snapshot, query_result, "action_required_field_missing")

    if slot.action_kind in _CREATE_ACTIONS:
        return _resolved(
            slot,
            snapshot,
            query_result=None,
            table_id=table.table_id,
            assignment_ids=assignment_ids,
            candidates=(),
        )

    if query_result is None:
        return _denied(slot, snapshot, None, "action_query_result_missing")
    if (
        query_result.scope_hash != snapshot.scope_hash
        or query_result.schema_hash != snapshot.schema_hash
    ):
        raise ValueError("action_candidate_scope_mismatch")
    if query_result.truncated:
        return _denied(slot, snapshot, query_result, "action_query_result_incomplete")
    versions = {
        item.record_id: (item.table_id, item.record_version)
        for item in query_result.source_versions
    }
    records = tuple(
        item for item in query_result.records if item.table_id == table.table_id
    )
    if not records:
        return _denied(slot, snapshot, query_result, "action_candidate_empty")
    if slot.target.expansion_policy == "none" and len(records) != 1:
        return _denied(slot, snapshot, query_result, "action_candidate_ambiguous")
    candidate_values: list[dict[str, object]] = []
    for record in sorted(records, key=lambda item: str(item.record_id)):
        current = versions.get(record.record_id)
        if current is None or current[0] != table.table_id:
            return _denied(slot, snapshot, query_result, "action_version_proof_missing")
        candidate_values.append(
            {
                "table_id": table.table_id,
                "record_id": record.record_id,
                "record_version": current[1],
                "writable_field_ids": tuple(sorted(assignment_ids, key=str)),
            }
        )
    return _resolved(
        slot,
        snapshot,
        query_result=query_result,
        table_id=table.table_id,
        assignment_ids=assignment_ids,
        candidates=tuple(candidate_values),
    )


def _resolve_table(slot, snapshot, query_result):
    table_id = slot.target.table_id
    if table_id is None and query_result is not None:
        ids = {item.table_id for item in query_result.records}
        if len(ids) == 1:
            table_id = next(iter(ids))
    return next((item for item in snapshot.tables if item.table_id == table_id), None)


def _resolved(
    slot,
    snapshot,
    *,
    query_result,
    table_id,
    assignment_ids,
    candidates,
):
    values = {
        "version": "stage12-authorized-candidates.v1",
        "objective_key": slot.objective_id,
        "slot_key": slot.slot_id,
        "action_kind": slot.action_kind,
        "status": "resolved",
        "target_table_ids": (table_id,),
        "candidates": candidates,
        "assignment_field_ids": tuple(sorted(assignment_ids, key=str)),
        "scope_hash": snapshot.scope_hash,
        "schema_hash": snapshot.schema_hash,
        "result_hash": None if query_result is None else query_result.result_hash,
        "complete": True,
        "denial_reason": None,
    }
    values["candidate_set_hash"] = action_candidate_sha256(_json_ready(values))
    return DurableAuthorizedCandidateSetV1.model_validate(values)


def _denied(slot, snapshot, query_result, reason):
    values = {
        "version": "stage12-authorized-candidates.v1",
        "objective_key": slot.objective_id,
        "slot_key": slot.slot_id,
        "action_kind": slot.action_kind,
        "status": "denied",
        "target_table_ids": (),
        "candidates": (),
        "assignment_field_ids": (),
        "scope_hash": snapshot.scope_hash,
        "schema_hash": snapshot.schema_hash,
        "result_hash": None if query_result is None else query_result.result_hash,
        "complete": False,
        "denial_reason": reason,
    }
    values["candidate_set_hash"] = action_candidate_sha256(_json_ready(values))
    return DurableAuthorizedCandidateSetV1.model_validate(values)


def _json_ready(value: dict[str, object]) -> dict[str, object]:
    # Reuse Pydantic's canonical JSON conversion without accepting extra fields.
    from pydantic import TypeAdapter

    return TypeAdapter(dict[str, object]).dump_python(value, mode="json")


__all__ = ["resolve_action_candidates"]
