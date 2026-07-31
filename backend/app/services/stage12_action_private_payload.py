from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
import re
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.schemas.stage12_action_runtime import ActionPrivatePayloadV1


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA_VERSION = "stage12-action-private.v1"


class Stage12ActionPrivatePayloadError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SealedStage12ActionPrivatePayload:
    ciphertext: bytes
    nonce: bytes
    key_version: str
    aad_hash: str
    scope_hash: str
    expires_at: datetime


def seal_stage12_action_private_payload(
    payload: ActionPrivatePayloadV1,
    *,
    key_b64: str,
    key_version: str,
    run_id: UUID,
    command_id: UUID,
    scope_hash: str,
) -> SealedStage12ActionPrivatePayload:
    key = _decode_key(key_b64)
    _require_scope_hash(scope_hash)
    if not key_version.strip() or len(key_version) > 80:
        raise Stage12ActionPrivatePayloadError(
            "action_private_payload_key_version_invalid"
        )
    aad = _aad(run_id, command_id, scope_hash)
    nonce = os.urandom(12)
    return SealedStage12ActionPrivatePayload(
        ciphertext=AESGCM(key).encrypt(
            nonce, payload.model_dump_json().encode("utf-8"), aad
        ),
        nonce=nonce,
        key_version=key_version,
        aad_hash=hashlib.sha256(aad).hexdigest(),
        scope_hash=scope_hash,
        expires_at=payload.expires_at,
    )


def open_stage12_action_private_payload(
    sealed: object,
    *,
    key_b64: str,
    run_id: UUID,
    command_id: UUID,
    scope_hash: str,
    now: datetime,
) -> ActionPrivatePayloadV1:
    if now >= sealed.expires_at:  # type: ignore[attr-defined]
        raise Stage12ActionPrivatePayloadError("action_private_payload_expired")
    _require_scope_hash(scope_hash)
    aad = _aad(run_id, command_id, scope_hash)
    if (
        getattr(sealed, "scope_hash", None) != scope_hash
        or getattr(sealed, "aad_hash", None) != hashlib.sha256(aad).hexdigest()
        or len(getattr(sealed, "nonce", b"")) != 12
    ):
        raise Stage12ActionPrivatePayloadError("action_private_payload_invalid")
    try:
        plaintext = AESGCM(_decode_key(key_b64)).decrypt(
            sealed.nonce,  # type: ignore[attr-defined]
            sealed.ciphertext,  # type: ignore[attr-defined]
            aad,
        )
        payload = ActionPrivatePayloadV1.model_validate_json(plaintext)
    except (
        InvalidTag,
        ValueError,
        TypeError,
        AttributeError,
        json.JSONDecodeError,
    ) as exc:
        raise Stage12ActionPrivatePayloadError(
            "action_private_payload_invalid"
        ) from exc
    if payload.expires_at != sealed.expires_at:  # type: ignore[attr-defined]
        raise Stage12ActionPrivatePayloadError("action_private_payload_invalid")
    return payload


def _aad(run_id: UUID, command_id: UUID, scope_hash: str) -> bytes:
    return json.dumps(
        {
            "command_id": str(command_id),
            "run_id": str(run_id),
            "schema_version": _SCHEMA_VERSION,
            "scope_hash": scope_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeError) as exc:
        raise Stage12ActionPrivatePayloadError(
            "action_private_payload_key_invalid"
        ) from exc
    if len(key) != 32:
        raise Stage12ActionPrivatePayloadError("action_private_payload_key_invalid")
    return key


def _require_scope_hash(value: str) -> None:
    if not _HASH_RE.fullmatch(value):
        raise Stage12ActionPrivatePayloadError("action_private_payload_scope_invalid")


__all__ = [
    "SealedStage12ActionPrivatePayload",
    "Stage12ActionPrivatePayloadError",
    "open_stage12_action_private_payload",
    "seal_stage12_action_private_payload",
]
