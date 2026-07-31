"""Outbox callbacks for Stage12 Retrieval V2 materialization."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import re
from uuid import UUID

from app.models.outbox import OutboxEvent
from app.schemas.retrieval_v2 import RetrievalProjectionV2
from app.services.retrieval_v2_indexing import (
    EmbeddingDocumentProvider,
    ProjectionReader,
    RetrievalIndexUnitOfWork,
    expand_retrieval_source_change_event,
    process_retrieval_projection_event,
)
from app.services.retrieval_v2_projection import TokenCounter
from app.services.retrieval_v2_registration import (
    RetrievalRegistrationDenied,
    build_registered_source_projections,
    process_registered_scope_bootstrap,
    read_registered_projection,
)
from app.services.stage06_platform import Stage06PlatformUnitOfWork
from app.workers.handlers import OutboxHandler
from app.workers.outbox_dispatcher import (
    NonRetryableOutboxError,
    RetryableOutboxError,
)


_SOURCE_CHANGE_EVENT = "stage12.retrieval_source.changed"
_PROJECTION_REQUEST_EVENT = "stage12.retrieval_projection.requested"
_PROJECTION_REVOKED_EVENT = "stage12.retrieval_projection.revoked"
_SCOPE_BOOTSTRAP_EVENT = "stage12.retrieval_scope.bootstrap_requested"
_REVOCATION_KEYS = frozenset(
    {
        "workspace_id",
        "source_type",
        "source_id",
        "source_ids",
        "visibility_profile_hash",
        "reason_code",
        "trace_id",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_REASON = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_RETRYABLE_ERRORS = frozenset(
    {
        "embedding_provider_unavailable",
        "embedding_provider_rate_limited",
        "retrieval_index_write_failed",
        "retrieval_projection_read_failed",
        "retrieval_source_projection_enqueue_failed",
        "retrieval_source_projection_read_failed",
    }
)


def build_retrieval_v2_outbox_handlers(
    *,
    uow: RetrievalIndexUnitOfWork,
    source_projection_reader: Callable[
        [dict[str, object]], tuple[RetrievalProjectionV2, ...]
    ],
    registered_scope_profiles: frozenset[tuple[str, str]],
    projection_reader: ProjectionReader,
    token_counter: TokenCounter,
    embedding_provider: EmbeddingDocumentProvider,
    now: Callable[[], datetime],
) -> dict[str, OutboxHandler]:
    """Build the bounded Retrieval V2 handlers used by the generic dispatcher."""

    def handle_source_change(event: OutboxEvent) -> None:
        result = expand_retrieval_source_change_event(
            uow,
            event,
            projection_reader=source_projection_reader,
            registered_scope_profiles=registered_scope_profiles,
            now=now(),
        )
        _raise_for_failure(result.status, result.error_code)

    def handle_projection_request(event: OutboxEvent) -> None:
        result = process_retrieval_projection_event(
            uow,
            event,
            projection_reader=projection_reader,
            token_counter=token_counter,
            provider=embedding_provider,
            now=now(),
        )
        _raise_for_failure(result.status, result.error_code)

    def handle_projection_revoked(event: OutboxEvent) -> None:
        if not _valid_revocation_event(event):
            raise NonRetryableOutboxError("retrieval_revocation_event_invalid")

    return {
        _SOURCE_CHANGE_EVENT: handle_source_change,
        _PROJECTION_REQUEST_EVENT: handle_projection_request,
        _PROJECTION_REVOKED_EVENT: handle_projection_revoked,
    }


def build_registered_retrieval_v2_outbox_handlers(
    *,
    platform_uow: Stage06PlatformUnitOfWork,
    uow: RetrievalIndexUnitOfWork,
    token_counter: TokenCounter,
    embedding_provider: EmbeddingDocumentProvider,
    now: Callable[[], datetime],
) -> dict[str, OutboxHandler]:
    """Build production handlers backed only by durable current registrations."""

    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (),
        registered_scope_profiles=frozenset(),
        projection_reader=lambda reference: read_registered_projection(
            platform_uow,
            uow,
            reference=reference,
            now=now(),
        ),
        token_counter=token_counter,
        embedding_provider=embedding_provider,
        now=now,
    )

    def handle_registered_source_change(event: OutboxEvent) -> None:
        event_now = now()
        try:
            projections = build_registered_source_projections(
                platform_uow,
                uow,
                reference=dict(event.payload),
                now=event_now,
            )
        except Exception:
            _raise_for_failure(
                "failed",
                "retrieval_source_projection_read_failed",
            )
            return
        profiles = frozenset(
            (projection.visibility_profile_hash, projection.scope_hash)
            for projection in projections
        )
        result = expand_retrieval_source_change_event(
            uow,
            event,
            projection_reader=lambda reference: projections,
            registered_scope_profiles=profiles,
            now=event_now,
        )
        _raise_for_failure(result.status, result.error_code)

    def handle_scope_bootstrap(event: OutboxEvent) -> None:
        try:
            process_registered_scope_bootstrap(
                platform_uow,
                uow,
                event=event,
                now=now(),
            )
        except RetrievalRegistrationDenied as exc:
            raise NonRetryableOutboxError(str(exc)) from None
        except Exception:
            raise RetryableOutboxError("retrieval_scope_bootstrap_failed") from None

    handlers[_SOURCE_CHANGE_EVENT] = handle_registered_source_change
    handlers[_SCOPE_BOOTSTRAP_EVENT] = handle_scope_bootstrap
    return handlers


def _raise_for_failure(status: str, error_code: str) -> None:
    if status != "failed":
        return
    if error_code in _RETRYABLE_ERRORS:
        raise RetryableOutboxError(error_code)
    raise NonRetryableOutboxError(error_code)


def _valid_revocation_event(event: OutboxEvent) -> bool:
    payload = event.payload
    if not (
        event.event_type == _PROJECTION_REVOKED_EVENT
        and event.aggregate_type == "stage12_retrieval_source"
        and event.status in {"processing", "processed"}
        and isinstance(payload, dict)
        and set(payload) == _REVOCATION_KEYS
        and payload.get("source_type")
        in {"schema_table", "schema_field", "record", "record_field"}
        and isinstance(payload.get("source_id"), str)
        and payload["source_id"] == event.aggregate_id
        and payload["source_id"] == payload["source_id"].strip()
        and bool(payload["source_id"])
        and len(payload["source_id"]) <= 240
        and "\r" not in payload["source_id"]
        and "\n" not in payload["source_id"]
        and isinstance(payload.get("source_ids"), (tuple, list))
        and _SHA256.fullmatch(str(payload.get("visibility_profile_hash"))) is not None
        and _SAFE_REASON.fullmatch(str(payload.get("reason_code"))) is not None
        and payload.get("trace_id") == event.trace_id
        and _SHA256.fullmatch(str(payload.get("trace_id"))) is not None
    ):
        return False
    try:
        UUID(str(payload["workspace_id"]))
        source_ids = tuple(str(item) for item in payload["source_ids"])
        if len(source_ids) != len(set(source_ids)) or source_ids != tuple(
            sorted(source_ids)
        ):
            return False
        for source_id in source_ids:
            UUID(source_id)
    except (TypeError, ValueError):
        return False
    return True


__all__ = [
    "build_registered_retrieval_v2_outbox_handlers",
    "build_retrieval_v2_outbox_handlers",
]
