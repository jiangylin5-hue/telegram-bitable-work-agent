from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.schemas.stage12_action_runtime import (
    ActionPrivatePayloadV1,
    ActionSlotControlV1,
    DurableAuthorizedCandidateSetV1,
)


class DurableActionSemanticError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def propose_durable_action(
    *,
    candidate_set: DurableAuthorizedCandidateSetV1,
    control: ActionSlotControlV1,
    private_payload: ActionPrivatePayloadV1,
    objective_key: str,
    slot_key: str,
    schema_hash: str,
    scope_hash: str,
    current_record_version: Callable[[UUID], tuple[UUID, int] | None],
) -> ActionPrivatePayloadV1:
    """Return a proposal only after exact authorization and semantic validation."""

    candidate_ids = tuple(item.record_id for item in candidate_set.candidates)
    candidate_versions = {
        item.record_id: (item.table_id, item.record_version)
        for item in candidate_set.candidates
    }
    payload_versions = {
        item.record_id: (item.table_id, item.record_version)
        for item in private_payload.record_versions
    }
    assignment_fields = {item.field_id for item in private_payload.assignments}
    control_fields = {item.field_id for item in control.editable_fields}
    writable_fields = {
        field_id
        for candidate in candidate_set.candidates
        for field_id in candidate.writable_field_ids
    }
    if not candidate_set.candidates:
        writable_fields = set(candidate_set.assignment_field_ids)
    if (
        candidate_set.status != "resolved"
        or not candidate_set.complete
        or candidate_set.objective_key != objective_key
        or candidate_set.slot_key != slot_key
        or private_payload.objective_key != objective_key
        or private_payload.slot_key != slot_key
        or candidate_set.action_kind != private_payload.action_kind
        or control.action_kind != private_payload.action_kind
        or control.confirmation_policy != "required"
        or candidate_set.candidate_set_hash != private_payload.candidate_set_hash
        or candidate_set.scope_hash != scope_hash
        or candidate_set.schema_hash != schema_hash
        or private_payload.target_table_id not in candidate_set.target_table_ids
        or candidate_ids != private_payload.target_record_ids
        or candidate_versions != payload_versions
        or not assignment_fields.issubset(set(candidate_set.assignment_field_ids))
        or not assignment_fields.issubset(control_fields)
        or not assignment_fields.issubset(writable_fields)
        or not set(private_payload.evidence_ids).issubset(set(control.evidence_refs))
    ):
        raise DurableActionSemanticError("action_candidate_scope_mismatch")

    required_fields = {
        item.field_id for item in control.editable_fields if item.required
    }
    if not required_fields.issubset(assignment_fields):
        raise DurableActionSemanticError("action_required_field_missing")

    if private_payload.action_kind in {"record.create", "task.create"}:
        if (
            candidate_ids
            or payload_versions
            or any(item.record_id is not None for item in private_payload.assignments)
        ):
            raise DurableActionSemanticError("action_target_invalid")
    else:
        if any(
            item.record_id not in set(candidate_ids)
            for item in private_payload.assignments
        ):
            raise DurableActionSemanticError("action_target_invalid")
        for candidate in candidate_set.candidates:
            if current_record_version(candidate.record_id) != (
                candidate.table_id,
                candidate.record_version,
            ):
                raise DurableActionSemanticError("action_candidate_version_drift")

    return private_payload


__all__ = [
    "DurableActionSemanticError",
    "propose_durable_action",
]
