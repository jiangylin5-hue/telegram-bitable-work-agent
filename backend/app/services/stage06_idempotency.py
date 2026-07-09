from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.models.stage06_hardening import Stage06IdempotencyRecord
from app.services.stage06_platform import PlatformValidationError


class Stage06IdempotencyUnitOfWork(Protocol):
    def get_idempotency_record(
        self,
        workspace_id: UUID,
        operation: str,
        idempotency_key: str,
    ) -> Stage06IdempotencyRecord | None:
        pass

    def add_idempotency_record(self, record: Stage06IdempotencyRecord) -> None:
        pass


@dataclass(frozen=True)
class IdempotencyDecision:
    status: str
    record: Stage06IdempotencyRecord
    response_ref: dict[str, Any] | None = None


def fingerprint_request(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def begin_idempotent_operation(
    uow: Stage06IdempotencyUnitOfWork,
    *,
    workspace_id: UUID,
    operation: str,
    idempotency_key: str,
    request_fingerprint: str,
    trace_id: str,
) -> IdempotencyDecision:
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise PlatformValidationError("idempotency_key_required", operation)
    existing = uow.get_idempotency_record(
        workspace_id,
        operation,
        normalized_key,
    )
    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise PlatformValidationError("idempotency_conflict", operation)
        if existing.status == "completed":
            return IdempotencyDecision(
                status="replay",
                record=existing,
                response_ref=existing.response_ref,
            )
        raise PlatformValidationError("idempotency_in_progress", operation)

    record = Stage06IdempotencyRecord(
        id=uuid4(),
        workspace_id=workspace_id,
        operation=operation,
        idempotency_key=normalized_key,
        request_fingerprint=request_fingerprint,
        status="in_progress",
        response_ref=None,
        trace_id=trace_id,
    )
    uow.add_idempotency_record(record)
    return IdempotencyDecision(status="started", record=record)


def complete_idempotent_operation(
    record: Stage06IdempotencyRecord,
    *,
    response_ref: dict[str, Any],
) -> None:
    record.status = "completed"
    record.response_ref = dict(response_ref)
