from datetime import UTC, datetime, timedelta
import base64
from dataclasses import replace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.schemas.agent_event_runtime import AgentPrivateInputPayload
from app.services.agent_private_inputs import (
    PrivateInputError,
    _aad,
    open_agent_private_input,
    seal_agent_private_input,
)


NOW = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
KEY = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")
SCOPE_HASH = "a" * 64


def _payload():
    return AgentPrivateInputPayload(
        actor_user_id="user-1",
        workspace_id=uuid4(),
        employee_id=uuid4(),
        intent="business_fact",
        query="请汇总逾期客户并说明依据",
        target_record_id=None,
        idempotency_key="stage10-private-input-1",
        skill_id="platform-tabular-analysis",
    )


def test_private_input_round_trip_persists_ciphertext_only() -> None:
    run_id = uuid4()
    command_id = uuid4()
    payload = _payload()

    sealed = seal_agent_private_input(
        payload,
        key_b64=KEY,
        key_version="stage10-v1",
        run_id=run_id,
        command_id=command_id,
        scope_hash=SCOPE_HASH,
        expires_at=NOW + timedelta(minutes=5),
    )

    assert payload.query.encode("utf-8") not in sealed.ciphertext
    assert open_agent_private_input(
        sealed,
        key_b64=KEY,
        run_id=run_id,
        command_id=command_id,
        scope_hash=SCOPE_HASH,
        now=NOW,
    ) == payload


@pytest.mark.parametrize("drift", ["run", "command", "scope"])
def test_private_input_rejects_authenticated_context_drift(drift: str) -> None:
    run_id = uuid4()
    command_id = uuid4()
    sealed = seal_agent_private_input(
        _payload(),
        key_b64=KEY,
        key_version="stage10-v1",
        run_id=run_id,
        command_id=command_id,
        scope_hash=SCOPE_HASH,
        expires_at=NOW + timedelta(minutes=5),
    )

    with pytest.raises(PrivateInputError, match="agent_private_input_invalid"):
        open_agent_private_input(
            sealed,
            key_b64=KEY,
            run_id=uuid4() if drift == "run" else run_id,
            command_id=uuid4() if drift == "command" else command_id,
            scope_hash="b" * 64 if drift == "scope" else SCOPE_HASH,
            now=NOW,
        )


def test_private_input_rejects_expired_ciphertext_and_wrong_key() -> None:
    run_id = uuid4()
    command_id = uuid4()
    sealed = seal_agent_private_input(
        _payload(),
        key_b64=KEY,
        key_version="stage10-v1",
        run_id=run_id,
        command_id=command_id,
        scope_hash=SCOPE_HASH,
        expires_at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(PrivateInputError, match="agent_private_input_expired"):
        open_agent_private_input(
            sealed,
            key_b64=KEY,
            run_id=run_id,
            command_id=command_id,
            scope_hash=SCOPE_HASH,
            now=NOW + timedelta(seconds=2),
        )
    with pytest.raises(PrivateInputError, match="agent_private_input_invalid"):
        open_agent_private_input(
            sealed,
            key_b64=base64.urlsafe_b64encode(b"z" * 32).decode("ascii"),
            run_id=run_id,
            command_id=command_id,
            scope_hash=SCOPE_HASH,
            now=NOW,
        )


def test_private_input_wraps_decrypted_schema_validation_failure() -> None:
    run_id = uuid4()
    command_id = uuid4()
    sealed = seal_agent_private_input(
        _payload(),
        key_b64=KEY,
        key_version="stage10-v1",
        run_id=run_id,
        command_id=command_id,
        scope_hash=SCOPE_HASH,
        expires_at=NOW + timedelta(minutes=5),
    )
    invalid_ciphertext = AESGCM(base64.urlsafe_b64decode(KEY)).encrypt(
        sealed.nonce,
        b"{}",
        _aad(run_id, command_id, SCOPE_HASH, "agent-private-input.v1"),
    )

    with pytest.raises(PrivateInputError, match="agent_private_input_invalid"):
        open_agent_private_input(
            replace(sealed, ciphertext=invalid_ciphertext),
            key_b64=KEY,
            run_id=run_id,
            command_id=command_id,
            scope_hash=SCOPE_HASH,
            now=NOW,
        )
