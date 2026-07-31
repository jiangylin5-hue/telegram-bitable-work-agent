from __future__ import annotations

from datetime import UTC, datetime
import json
from uuid import uuid4

import pytest

from app.schemas.stage12_action_runtime import (
    ActionPrivatePayloadV1,
    ActionSlotControlV1,
    DurableAuthorizedCandidateSetV1,
    action_candidate_sha256,
)
from app.services.stage12_durable_action_specialist import (
    DurableActionSemanticError,
    propose_durable_action,
)


def _fixture():
    table_id = uuid4()
    record_id = uuid4()
    field_id = uuid4()
    values = {
        "version": "stage12-authorized-candidates.v1",
        "objective_key": "obj-01",
        "slot_key": "slot-01",
        "action_kind": "record.update",
        "status": "resolved",
        "target_table_ids": (str(table_id),),
        "candidates": (
            {
                "table_id": str(table_id),
                "record_id": str(record_id),
                "record_version": 3,
                "writable_field_ids": (str(field_id),),
            },
        ),
        "assignment_field_ids": (str(field_id),),
        "scope_hash": "a" * 64,
        "schema_hash": "b" * 64,
        "result_hash": None,
        "complete": True,
        "denial_reason": None,
    }
    values["candidate_set_hash"] = action_candidate_sha256(values)
    candidates = DurableAuthorizedCandidateSetV1.model_validate_json(json.dumps(values))
    control = ActionSlotControlV1(
        action_kind="record.update",
        confirmation_policy="required",
        dependency_keys=(),
        evidence_refs=("ev-01",),
        editable_fields=(
            {
                "field_id": field_id,
                "field_key": "status",
                "label": "状态",
                "field_type": "status",
                "required": True,
            },
        ),
        safe_summary="更新一条授权记录",
    )
    payload = ActionPrivatePayloadV1(
        actor_user_id="operator-1",
        objective_key="obj-01",
        slot_key="slot-01",
        action_kind="record.update",
        candidate_set_hash=candidates.candidate_set_hash,
        target_table_id=table_id,
        target_record_ids=(record_id,),
        assignments=({"record_id": record_id, "field_id": field_id, "value": "done"},),
        record_versions=(
            {"table_id": table_id, "record_id": record_id, "record_version": 3},
        ),
        evidence_ids=("ev-01",),
        expires_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
    )
    return candidates, control, payload, table_id, record_id, field_id


def test_durable_action_specialist_returns_only_semantically_validated_proposal() -> (
    None
):
    candidates, control, payload, table_id, record_id, _field_id = _fixture()

    proposal = propose_durable_action(
        candidate_set=candidates,
        control=control,
        private_payload=payload,
        objective_key="obj-01",
        slot_key="slot-01",
        schema_hash="b" * 64,
        scope_hash="a" * 64,
        current_record_version=lambda value: (
            (
                table_id,
                3,
            )
            if value == record_id
            else None
        ),
    )

    assert proposal is payload
    assert proposal.target_record_ids == (record_id,)
    assert proposal.assignments[0].value == "done"


def test_durable_action_specialist_rejects_field_scope_and_version_drift() -> None:
    candidates, control, payload, table_id, record_id, _field_id = _fixture()
    unauthorized_field = uuid4()
    changed = payload.model_copy(
        update={
            "assignments": (
                payload.assignments[0].model_copy(
                    update={"field_id": unauthorized_field}
                ),
            )
        }
    )

    with pytest.raises(
        DurableActionSemanticError, match="action_candidate_scope_mismatch"
    ):
        propose_durable_action(
            candidate_set=candidates,
            control=control,
            private_payload=changed,
            objective_key="obj-01",
            slot_key="slot-01",
            schema_hash="b" * 64,
            scope_hash="a" * 64,
            current_record_version=lambda _value: (table_id, 3),
        )

    with pytest.raises(
        DurableActionSemanticError, match="action_candidate_version_drift"
    ):
        propose_durable_action(
            candidate_set=candidates,
            control=control,
            private_payload=payload,
            objective_key="obj-01",
            slot_key="slot-01",
            schema_hash="b" * 64,
            scope_hash="a" * 64,
            current_record_version=lambda value: (
                (
                    table_id,
                    4,
                )
                if value == record_id
                else None
            ),
        )
