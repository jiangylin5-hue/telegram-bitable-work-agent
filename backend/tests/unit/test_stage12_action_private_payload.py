from datetime import UTC, datetime, timedelta
import base64
from uuid import uuid4

import pytest

from app.schemas.stage12_action_runtime import ActionPrivatePayloadV1
from app.services.stage12_action_private_payload import (
    Stage12ActionPrivatePayloadError,
    open_stage12_action_private_payload,
    seal_stage12_action_private_payload,
)


KEY = base64.urlsafe_b64encode(b"x" * 32).decode("ascii")


def _payload() -> ActionPrivatePayloadV1:
    table_id = uuid4()
    record_id = uuid4()
    return ActionPrivatePayloadV1(
        actor_user_id="operator-1",
        objective_key="obj-01",
        slot_key="act-01",
        action_kind="record.update",
        candidate_set_hash="a" * 64,
        target_table_id=table_id,
        target_record_ids=(record_id,),
        assignments=(
            {"record_id": record_id, "field_id": uuid4(), "value": "secret-value"},
        ),
        record_versions=(
            {"table_id": table_id, "record_id": record_id, "record_version": 2},
        ),
        evidence_ids=("ev-01",),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def test_action_private_payload_round_trip_and_ciphertext_redaction() -> None:
    run_id = uuid4()
    command_id = uuid4()
    payload = _payload()
    sealed = seal_stage12_action_private_payload(
        payload,
        key_b64=KEY,
        key_version="test-key-v1",
        run_id=run_id,
        command_id=command_id,
        scope_hash="b" * 64,
    )

    assert b"secret-value" not in sealed.ciphertext
    assert (
        open_stage12_action_private_payload(
            sealed,
            key_b64=KEY,
            run_id=run_id,
            command_id=command_id,
            scope_hash="b" * 64,
            now=datetime.now(UTC),
        )
        == payload
    )


def test_action_private_payload_rejects_scope_drift_and_expiry() -> None:
    run_id = uuid4()
    command_id = uuid4()
    payload = _payload()
    sealed = seal_stage12_action_private_payload(
        payload,
        key_b64=KEY,
        key_version="test-key-v1",
        run_id=run_id,
        command_id=command_id,
        scope_hash="b" * 64,
    )

    with pytest.raises(
        Stage12ActionPrivatePayloadError, match="action_private_payload_invalid"
    ):
        open_stage12_action_private_payload(
            sealed,
            key_b64=KEY,
            run_id=run_id,
            command_id=command_id,
            scope_hash="c" * 64,
            now=datetime.now(UTC),
        )
    with pytest.raises(
        Stage12ActionPrivatePayloadError, match="action_private_payload_expired"
    ):
        open_stage12_action_private_payload(
            sealed,
            key_b64=KEY,
            run_id=run_id,
            command_id=command_id,
            scope_hash="b" * 64,
            now=payload.expires_at,
        )
