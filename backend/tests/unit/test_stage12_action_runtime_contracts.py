from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.stage12_action_runtime import (
    ActionConfirmRequestV1,
    ActionPrivatePayloadV1,
    ActionSlotControlV1,
    ObjectiveRunCreateV1,
)


def test_objective_contract_rejects_duplicate_dependency_keys() -> None:
    with pytest.raises(ValidationError, match="objective_dependency_duplicate"):
        ObjectiveRunCreateV1(
            objective_key="obj-01",
            kind="tabular",
            required=True,
            dependency_keys=("obj-00", "obj-00"),
        )


def test_action_control_contains_no_private_assignments_or_target() -> None:
    control = ActionSlotControlV1(
        action_kind="record.update",
        confirmation_policy="required",
        dependency_keys=("obj-01",),
        evidence_refs=("evidence:01",),
        editable_fields=(
            {
                "field_id": uuid4(),
                "field_key": "status",
                "label": "状态",
                "field_type": "single_select",
                "required": True,
            },
        ),
        safe_summary="更新一条授权记录",
    )

    payload = control.model_dump(mode="json")
    assert "assignments" not in payload
    assert "target" not in payload
    assert "message_payload" not in payload


def test_private_payload_binds_candidate_and_versions() -> None:
    record_id = uuid4()
    table_id = uuid4()
    payload = ActionPrivatePayloadV1(
        actor_user_id="operator-1",
        objective_key="obj-02",
        slot_key="act-01",
        action_kind="record.update",
        candidate_set_hash="a" * 64,
        target_table_id=table_id,
        target_record_ids=(record_id,),
        assignments=({"record_id": record_id, "field_id": uuid4(), "value": "done"},),
        record_versions=(
            {"table_id": table_id, "record_id": record_id, "record_version": 3},
        ),
        evidence_ids=("ev-01",),
        expires_at=datetime(2026, 7, 31, tzinfo=UTC),
    )
    assert payload.schema_version == "stage12-action-private.v1"


def test_confirm_rejects_client_supplied_action_kind() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ActionConfirmRequestV1(
            proposal_version=1,
            record_version=None,
            proposed_values={"status": "done"},
            action_kind="record.update",
        )
