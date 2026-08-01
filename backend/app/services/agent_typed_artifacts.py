from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.models.agent_event_runtime import AgentArtifact
from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.schemas.agent_specialist_results import specialist_payload_sha256
from app.schemas.agent_stage12_runtime import Stage12ObjectiveDispatchV1
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)


_OPERATION = "stage12.specialist-artifact.v1"
_OWNER_VERSION = "typed-artifact-owner.v1"
_STORAGE_REF = re.compile(
    r"^stage08-idempotency:([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)
_OWNER_KEYS = {
    "version",
    "artifact_kind",
    "payload_version",
    "scope_hash",
    "content_hash",
    "payload",
}
_HASH_FIELDS = (
    "content_hash",
    "candidate_set_hash",
    "observation_hash",
    "bundle_hash",
)
_VERSIONLESS_PAYLOAD_TYPES = {"ActionSlotV1": "action-slot.v1"}


class TypedArtifactUnitOfWork(Protocol):
    def get_idempotency_record(
        self, workspace_id: UUID, operation: str, idempotency_key: str
    ) -> Stage06IdempotencyRecord | None: ...

    def get_idempotency_record_by_id(
        self, record_id: UUID
    ) -> Stage06IdempotencyRecord | None: ...

    def add_idempotency_record(self, record: Stage06IdempotencyRecord) -> None: ...

    def flush(self) -> None: ...


@dataclass(frozen=True, slots=True)
class TypedArtifactOwner:
    owner_id: UUID
    storage_ref: str
    artifact_kind: str
    content_hash: str
    replayed: bool


PayloadT = TypeVar("PayloadT", bound=BaseModel)


def stage12_command_input_artifact_ids(
    dispatch: Stage12ObjectiveDispatchV1,
) -> tuple[UUID, ...]:
    return (dispatch.objective_artifact_id, *dispatch.dependency_artifact_ids)


def persist_typed_artifact(
    uow: TypedArtifactUnitOfWork,
    *,
    workspace_id: UUID,
    run_id: UUID,
    artifact_kind: str,
    payload: BaseModel,
    scope_hash: str,
) -> TypedArtifactOwner:
    if not artifact_kind or not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", artifact_kind):
        raise ValueError("typed_artifact_kind_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", scope_hash):
        raise ValueError("typed_artifact_scope_invalid")
    payload_json = payload.model_dump(mode="json")
    payload_version = payload_json.get("version") or _VERSIONLESS_PAYLOAD_TYPES.get(
        type(payload).__name__
    )
    if not isinstance(payload_version, str) or not payload_version:
        raise ValueError("typed_artifact_payload_version_invalid")
    content_hash = _declared_payload_hash(payload_json)
    if content_hash != _computed_payload_hash(payload_json):
        raise ValueError("typed_artifact_payload_hash_mismatch")
    owner_payload = {
        "version": _OWNER_VERSION,
        "artifact_kind": artifact_kind,
        "payload_version": payload_version,
        "scope_hash": scope_hash,
        "content_hash": content_hash,
        "payload": payload_json,
    }
    request_fingerprint = fingerprint_request(owner_payload)
    idempotency_key = hashlib.sha256(
        f"{run_id}:{artifact_kind}:{content_hash}".encode("utf-8")
    ).hexdigest()
    decision = begin_idempotent_operation(
        uow,
        workspace_id=workspace_id,
        operation=_OPERATION,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        trace_id=idempotency_trace_id(_OPERATION, request_fingerprint, idempotency_key),
    )
    if decision.status == "replay":
        if decision.response_ref != owner_payload:
            raise ValueError("typed_artifact_owner_replay_mismatch")
    else:
        complete_idempotent_operation(decision.record, response_ref=owner_payload)
        uow.flush()
    return TypedArtifactOwner(
        owner_id=decision.record.id,
        storage_ref=f"stage08-idempotency:{decision.record.id}",
        artifact_kind=artifact_kind,
        content_hash=content_hash,
        replayed=decision.status == "replay",
    )


def read_typed_artifact(
    uow: TypedArtifactUnitOfWork,
    *,
    artifact: AgentArtifact,
    workspace_id: UUID,
    current_scope_hash: str,
    expected_kind: str,
    payload_type: type[PayloadT],
) -> PayloadT:
    if artifact.kind != expected_kind:
        raise ValueError("typed_artifact_kind_mismatch")
    if artifact.validation_status != "validated":
        raise ValueError("typed_artifact_validation_status_invalid")
    if artifact.visibility_scope_hash != current_scope_hash or not re.fullmatch(
        r"[0-9a-f]{64}", current_scope_hash
    ):
        raise ValueError("typed_artifact_scope_mismatch")
    return read_typed_artifact_owner_ref(
        uow,
        storage_ref=artifact.storage_ref,
        workspace_id=workspace_id,
        current_scope_hash=current_scope_hash,
        expected_kind=expected_kind,
        payload_type=payload_type,
        expected_content_hash=artifact.content_hash,
    )


def read_typed_artifact_owner_ref(
    uow: TypedArtifactUnitOfWork,
    *,
    storage_ref: str,
    workspace_id: UUID,
    current_scope_hash: str,
    expected_kind: str,
    payload_type: type[PayloadT],
    expected_content_hash: str | None = None,
) -> PayloadT:
    if not re.fullmatch(r"[0-9a-f]{64}", current_scope_hash):
        raise ValueError("typed_artifact_scope_mismatch")
    match = _STORAGE_REF.fullmatch(storage_ref)
    if match is None:
        raise ValueError("typed_artifact_storage_ref_invalid")
    record = uow.get_idempotency_record_by_id(UUID(match.group(1)))
    if (
        record is None
        or record.workspace_id != workspace_id
        or record.operation != _OPERATION
        or record.status != "completed"
        or not isinstance(record.response_ref, dict)
        or set(record.response_ref) != _OWNER_KEYS
    ):
        raise ValueError("typed_artifact_owner_invalid")
    owner = record.response_ref
    if (
        owner["version"] != _OWNER_VERSION
        or owner["artifact_kind"] != expected_kind
        or owner["scope_hash"] != current_scope_hash
        or (
            expected_content_hash is not None
            and owner["content_hash"] != expected_content_hash
        )
        or not isinstance(owner["payload"], dict)
    ):
        raise ValueError("typed_artifact_owner_mismatch")
    payload_json = owner["payload"]
    payload_version = payload_json.get("version") or _VERSIONLESS_PAYLOAD_TYPES.get(
        payload_type.__name__
    )
    if (
        owner["payload_version"] != payload_version
        or _declared_payload_hash(payload_json) != owner["content_hash"]
        or _computed_payload_hash(payload_json) != owner["content_hash"]
    ):
        raise ValueError("typed_artifact_payload_hash_mismatch")
    return payload_type.model_validate_json(
        json.dumps(
            payload_json,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _declared_payload_hash(payload: dict[str, object]) -> str:
    matches = [key for key in _HASH_FIELDS if key in payload]
    if len(matches) > 1:
        raise ValueError("typed_artifact_payload_hash_invalid")
    if not matches:
        return specialist_payload_sha256(payload)
    if not isinstance(payload[matches[0]], str):
        raise ValueError("typed_artifact_payload_hash_invalid")
    return str(payload[matches[0]])


def _computed_payload_hash(payload: dict[str, object]) -> str:
    hash_field = next((key for key in _HASH_FIELDS if key in payload), None)
    if hash_field is None:
        return specialist_payload_sha256(payload)
    return specialist_payload_sha256(
        {key: value for key, value in payload.items() if key != hash_field}
    )


__all__ = [
    "TypedArtifactOwner",
    "TypedArtifactUnitOfWork",
    "persist_typed_artifact",
    "read_typed_artifact",
    "read_typed_artifact_owner_ref",
    "stage12_command_input_artifact_ids",
]
