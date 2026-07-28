from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import base64
import hashlib
import json
import os
import re
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.schemas.agent_event_runtime import AgentPrivateInputPayload


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class PrivateInputError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SealedAgentPrivateInput:
    ciphertext: bytes
    nonce: bytes
    key_version: str
    aad_hash: str
    scope_hash: str
    expires_at: datetime


def seal_agent_private_input(
    payload: AgentPrivateInputPayload,
    *,
    key_b64: str,
    key_version: str,
    run_id: UUID,
    command_id: UUID,
    scope_hash: str,
    expires_at: datetime,
) -> SealedAgentPrivateInput:
    key = _decode_key(key_b64)
    if not key_version.strip() or len(key_version) > 80:
        raise PrivateInputError("agent_private_input_key_version_invalid")
    _require_scope_hash(scope_hash)
    aad = _aad(run_id, command_id, scope_hash, payload.schema_version)
    nonce = os.urandom(12)
    plaintext = payload.model_dump_json().encode("utf-8")
    return SealedAgentPrivateInput(
        ciphertext=AESGCM(key).encrypt(nonce, plaintext, aad),
        nonce=nonce,
        key_version=key_version,
        aad_hash=hashlib.sha256(aad).hexdigest(),
        scope_hash=scope_hash,
        expires_at=expires_at,
    )


def open_agent_private_input(
    sealed: object,
    *,
    key_b64: str,
    run_id: UUID,
    command_id: UUID,
    scope_hash: str,
    now: datetime,
) -> AgentPrivateInputPayload:
    if now >= sealed.expires_at:  # type: ignore[attr-defined]
        raise PrivateInputError("agent_private_input_expired")
    _require_scope_hash(scope_hash)
    aad = _aad(run_id, command_id, scope_hash, "agent-private-input.v1")
    if (
        getattr(sealed, "scope_hash", None) != scope_hash
        or getattr(sealed, "aad_hash", None) != hashlib.sha256(aad).hexdigest()
        or len(getattr(sealed, "nonce", b"")) != 12
    ):
        raise PrivateInputError("agent_private_input_invalid")
    try:
        plaintext = AESGCM(_decode_key(key_b64)).decrypt(
            sealed.nonce,  # type: ignore[attr-defined]
            sealed.ciphertext,  # type: ignore[attr-defined]
            aad,
        )
        return AgentPrivateInputPayload.model_validate_json(plaintext)
    except (InvalidTag, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise PrivateInputError("agent_private_input_invalid") from exc


def _aad(run_id: UUID, command_id: UUID, scope_hash: str, schema_version: str) -> bytes:
    return json.dumps(
        {
            "command_id": str(command_id),
            "run_id": str(run_id),
            "schema_version": schema_version,
            "scope_hash": scope_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeError) as exc:
        raise PrivateInputError("agent_private_input_key_invalid") from exc
    if len(key) != 32:
        raise PrivateInputError("agent_private_input_key_invalid")
    return key


def _require_scope_hash(value: str) -> None:
    if not _HASH_RE.fullmatch(value):
        raise PrivateInputError("agent_private_input_scope_invalid")


__all__ = [
    "PrivateInputError",
    "SealedAgentPrivateInput",
    "open_agent_private_input",
    "seal_agent_private_input",
]
