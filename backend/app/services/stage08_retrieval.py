from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import math
import re
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models.outbox import OutboxEvent
from app.models.stage06_platform import Workspace, WorkspaceMember
from app.models.stage08_knowledge import (
    Stage08KnowledgeChunk,
    Stage08KnowledgeSource,
)
from app.models.stage08_memory import Stage08MemoryItem
from app.runtime.stage08_memory_contracts import (
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.runtime.stage08_retrieval_contracts import KnowledgeSourceProjection
from app.services.audit import record_audit_event
from app.services.permissions import Actor
from app.services.stage06_authorization import action_allowed_for_role
from app.services.stage06_idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
    fingerprint_request,
    idempotency_trace_id,
)
from app.services.stage06_platform import (
    PlatformValidationError,
    SqlAlchemyStage06PlatformUnitOfWork,
    Stage06PlatformUnitOfWork,
)
from app.services.stage08_memory import read_memory_projection
from app.services.stage08_retrieval_chunking import (
    canonicalize_knowledge_text,
    chunk_knowledge_projection,
)
from app.services.stage08_retrieval_embeddings import (
    TEST_EMBEDDING_DIMENSION,
    TEST_EMBEDDING_PROFILE,
    TEST_EMBEDDING_VERSION,
    EmbeddingProvider,
    EmbeddingProviderUnavailable,
    UnavailableEmbeddingProvider,
    deterministic_test_hash_embedding,
)


_INDEX_EVENT_TYPE = "stage08.knowledge.index_requested"
_CLEANUP_EVENT_TYPE = "stage08.knowledge.cleanup_requested"
_REINDEX_OPERATION = "stage08.knowledge_reindex"
_REFERENCE_PAYLOAD_KEYS = frozenset(
    {
        "workspace_id",
        "knowledge_source_id",
        "content_version",
        "projection_hash",
        "trace_id",
    }
)
_MEMORY_PROJECTION_KEYS = frozenset(
    {"id", "memory_type", "version", "scope", "payload", "valid_until"}
)
_MEMORY_SCOPE_KEYS = frozenset(
    {
        "workspace_id",
        "base_id",
        "table_id",
        "customer_record_id",
        "project_record_id",
    }
)
_FORBIDDEN_PROJECTION_KEYS = frozenset(
    {
        "id",
        "item_id",
        "memory_item_id",
        "workspace_id",
        "base_id",
        "table_id",
        "customer_record_id",
        "project_record_id",
        "identity_token",
        "group_chat_ref",
        "source_id",
        "source_ref",
        "source_refs",
        "field_keys",
        "prompt",
        "response",
        "raw_text",
        "raw_caption",
        "normalized_text",
        "message_text",
        "chat_text",
        "transcript",
        "raw_content",
        "telegram_chat_id",
        "telegram_message_id",
        "telegram_update_id",
        "binding_id",
        "transport",
        "api_key",
        "token",
    }
)
_SAFE_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


@dataclass(frozen=True, slots=True, repr=False)
class KnowledgeSourceRegistration:
    source: Stage08KnowledgeSource = field(repr=False)
    event: OutboxEvent = field(repr=False)

    @property
    def outbox_payload(self) -> dict:
        return dict(self.event.payload)

    def __repr__(self) -> str:
        return (
            "KnowledgeSourceRegistration("
            f"status={self.source.status!r}, "
            f"content_version={self.source.content_version!r})"
        )


@dataclass(frozen=True, slots=True, repr=False)
class KnowledgeSourceLifecycleResult:
    source: Stage08KnowledgeSource = field(repr=False)
    event: OutboxEvent = field(repr=False)

    @property
    def outbox_payload(self) -> dict:
        return dict(self.event.payload)

    def __repr__(self) -> str:
        return (
            "KnowledgeSourceLifecycleResult("
            f"status={self.source.status!r}, "
            f"content_version={self.source.content_version!r})"
        )


@dataclass(frozen=True, slots=True, repr=False)
class KnowledgeReindexReceipt:
    ticket_id: UUID = field(repr=False)
    status: str = "accepted"

    def __repr__(self) -> str:
        return f"KnowledgeReindexReceipt(status={self.status!r})"


@dataclass(frozen=True, slots=True)
class KnowledgeIndexResult:
    status: str
    indexed_chunk_count: int = 0
    error_code: str = "none"


@dataclass(frozen=True, slots=True)
class KnowledgeCleanupResult:
    status: str
    cleaned_chunk_count: int = 0
    error_code: str = "none"


def request_knowledge_reindex(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    source_id: UUID,
    *,
    actor: Actor,
    idempotency_key: str,
    trace_id: str,
    now: datetime,
) -> KnowledgeReindexReceipt:
    if (
        not isinstance(workspace_id, UUID)
        or not isinstance(source_id, UUID)
        or not _valid_reindex_idempotency_key(idempotency_key)
        or not _valid_trace_id(trace_id)
    ):
        raise PlatformValidationError(
            "knowledge_reindex_request_invalid",
            "knowledge_reindex_request_invalid",
        )

    workspace = _lock_current_reindex_workspace(uow, workspace_id)
    if (
        workspace is None
        or getattr(workspace, "status", None) != "active"
        or not _actor_has_current_reindex_authority(uow, workspace_id, actor)
    ):
        raise PlatformValidationError(
            "knowledge_reindex_forbidden",
            "knowledge_reindex_forbidden",
        )

    source = _lock_current_reindex_source(uow, source_id)
    if source is None or source.workspace_id != workspace_id:
        raise PlatformValidationError(
            "knowledge_reindex_forbidden",
            "knowledge_reindex_forbidden",
        )
    if isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        with uow.session.no_autoflush:
            source_is_reindexable = _memory_source_is_reindexable(
                uow,
                source,
                actor=actor,
                now=now,
            )
    else:
        source_is_reindexable = _memory_source_is_reindexable(
            uow,
            source,
            actor=actor,
            now=now,
        )
    if not source_is_reindexable:
        raise PlatformValidationError(
            "knowledge_reindex_source_invalid",
            "knowledge_reindex_source_invalid",
        )

    semantic_payload = {
        "workspace_id": str(workspace_id),
        "knowledge_source_id": str(source_id),
        "actor_id": actor.actor_id,
        "trace_id": trace_id,
    }
    request_fingerprint = fingerprint_request(semantic_payload)
    decision = begin_idempotent_operation(
        uow,
        workspace_id=workspace_id,
        operation=_REINDEX_OPERATION,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        trace_id=idempotency_trace_id(
            _REINDEX_OPERATION,
            request_fingerprint,
            idempotency_key,
        ),
    )
    if decision.status == "replay":
        return _reindex_receipt_from_replay(uow, source, decision.response_ref)

    event = _get_or_create_reference_event(
        uow,
        source=source,
        event_type=_INDEX_EVENT_TYPE,
        trace_id=trace_id,
        now=now,
    )
    if event is None:
        _discard_reindex_idempotency_reservation(uow, decision.record)
        raise PlatformValidationError(
            "knowledge_reindex_source_invalid",
            "knowledge_reindex_source_invalid",
        )

    receipt = KnowledgeReindexReceipt(ticket_id=event.id)
    complete_idempotent_operation(
        decision.record,
        response_ref={"ticket_id": str(receipt.ticket_id), "status": receipt.status},
    )
    record_audit_event(
        getattr(uow, "session", uow),
        trace_id=decision.record.trace_id,
        actor_type="user",
        actor_id=actor.actor_id,
        event_type="stage08.knowledge.reindex_requested",
        entity_type="stage08_knowledge_reindex",
        entity_id=event.id,
        after_state={
            "status": receipt.status,
            "event_type": _INDEX_EVENT_TYPE,
            "source_type": source.source_type,
            "content_version": source.content_version,
        },
        permission_snapshot={"action": "member.manage", "role": actor.role},
    )
    return receipt


def process_knowledge_index_event(
    uow: Stage06PlatformUnitOfWork,
    event: OutboxEvent,
    *,
    provider: EmbeddingProvider | None = None,
    now: datetime,
) -> KnowledgeIndexResult:
    reference = _validate_reference_event(event, _INDEX_EVENT_TYPE)
    if reference is None:
        return KnowledgeIndexResult(
            status="failed",
            error_code="knowledge_index_source_invalid",
        )
    workspace_id, source_id, content_version, projection_hash = reference
    try:
        source = uow.lock_knowledge_source_for_lifecycle(source_id)
    except Exception:
        return KnowledgeIndexResult(
            status="failed",
            error_code="knowledge_index_failed",
        )
    if not _source_matches_index_reference(
        source,
        workspace_id=workspace_id,
        content_version=content_version,
        projection_hash=projection_hash,
        now=now,
    ):
        _mark_event_processed(event, now)
        return KnowledgeIndexResult(
            status="discarded",
            error_code="knowledge_index_source_invalid",
        )

    assert source is not None
    try:
        canonical_text = canonicalize_knowledge_text(source.projection_text)
        if _sha256(canonical_text) != source.projection_hash:
            raise ValueError("knowledge_index_source_invalid")
        chunk_projections = chunk_knowledge_projection(canonical_text)
    except (TypeError, ValueError):
        _mark_event_processed(event, now)
        return KnowledgeIndexResult(
            status="discarded",
            error_code="knowledge_index_source_invalid",
        )

    try:
        existing_chunks = uow.list_knowledge_chunks(
            source.id,
            source.content_version,
        )
    except Exception:
        return KnowledgeIndexResult(
            status="failed",
            error_code="knowledge_index_failed",
        )
    if existing_chunks:
        if _existing_index_matches(source, existing_chunks, chunk_projections):
            _mark_event_processed(event, now)
            return KnowledgeIndexResult(
                status="indexed",
                indexed_chunk_count=len(existing_chunks),
            )
        _scrub_conflicting_chunks(source, existing_chunks, now)
        return KnowledgeIndexResult(
            status="failed",
            error_code="knowledge_index_failed",
        )
    if event.status == "processed":
        return KnowledgeIndexResult(
            status="failed",
            error_code="knowledge_index_failed",
        )

    selected_provider = provider or UnavailableEmbeddingProvider()
    if not _valid_embedding_provider_profile(selected_provider):
        return KnowledgeIndexResult(
            status="failed",
            error_code="embedding_output_invalid",
        )
    texts = tuple(
        projection.chunk_text or "" for projection in chunk_projections
    )
    try:
        raw_embeddings = selected_provider.embed_batch(
            TEST_EMBEDDING_PROFILE,
            texts,
        )
    except EmbeddingProviderUnavailable:
        return KnowledgeIndexResult(
            status="failed",
            error_code="embedding_provider_unavailable",
        )
    except Exception:
        return KnowledgeIndexResult(
            status="failed",
            error_code="knowledge_index_failed",
        )
    embeddings = _validated_embeddings(raw_embeddings, len(chunk_projections))
    if embeddings is None:
        return KnowledgeIndexResult(
            status="failed",
            error_code="embedding_output_invalid",
        )

    pending_chunks = [
        Stage08KnowledgeChunk(
            id=uuid4(),
            workspace_id=source.workspace_id,
            source_id=source.id,
            source_version=source.content_version,
            ordinal=projection.ordinal,
            chunk_text=projection.chunk_text,
            chunk_hash=projection.chunk_hash,
            keyword_terms=list(projection.keyword_terms),
            embedding_profile=TEST_EMBEDDING_PROFILE,
            embedding_version=TEST_EMBEDDING_VERSION,
            embedding=list(embedding),
            status="pending",
            created_at=now,
            updated_at=now,
        )
        for projection, embedding in zip(
            chunk_projections,
            embeddings,
            strict=True,
        )
    ]
    try:
        for chunk in pending_chunks:
            uow.add_knowledge_chunk(chunk)
        for chunk in pending_chunks:
            chunk.status = "indexed"
    except Exception:
        for chunk in pending_chunks:
            chunk.status = "failed"
            chunk.chunk_text = None
            chunk.keyword_terms = []
            chunk.embedding = None
            chunk.embedding_profile = None
            chunk.embedding_version = None
        return KnowledgeIndexResult(
            status="failed",
            error_code="knowledge_index_failed",
        )

    _mark_event_processed(event, now)
    return KnowledgeIndexResult(
        status="indexed",
        indexed_chunk_count=len(pending_chunks),
    )


def process_knowledge_cleanup_event(
    uow: Stage06PlatformUnitOfWork,
    event: OutboxEvent,
    *,
    now: datetime,
) -> KnowledgeCleanupResult:
    reference = _validate_reference_event(event, _CLEANUP_EVENT_TYPE)
    if reference is None:
        return KnowledgeCleanupResult(
            status="failed",
            error_code="knowledge_index_source_invalid",
        )
    workspace_id, source_id, content_version, projection_hash = reference
    try:
        source = uow.lock_knowledge_source_for_lifecycle(source_id)
    except Exception:
        return KnowledgeCleanupResult(
            status="failed",
            error_code="knowledge_index_failed",
        )
    if not _source_matches_cleanup_reference(
        source,
        workspace_id=workspace_id,
        content_version=content_version,
        projection_hash=projection_hash,
    ):
        _mark_event_processed(event, now)
        return KnowledgeCleanupResult(
            status="discarded",
            error_code="knowledge_index_source_invalid",
        )

    assert source is not None
    try:
        chunks = uow.list_knowledge_chunks(source.id, source.content_version)
    except Exception:
        return KnowledgeCleanupResult(
            status="failed",
            error_code="knowledge_index_failed",
        )
    if any(
        chunk.workspace_id != source.workspace_id
        or chunk.source_id != source.id
        or chunk.source_version != source.content_version
        for chunk in chunks
    ):
        return KnowledgeCleanupResult(
            status="failed",
            error_code="knowledge_index_failed",
        )

    source.projection_text = None
    source.updated_at = now
    for chunk in chunks:
        chunk.chunk_text = None
        chunk.keyword_terms = []
        chunk.embedding = None
        chunk.embedding_profile = None
        chunk.embedding_version = None
        chunk.status = "deleted"
        if chunk.deleted_at is None:
            chunk.deleted_at = now
        chunk.updated_at = now
    _mark_event_processed(event, now)
    return KnowledgeCleanupResult(
        status="cleaned",
        cleaned_chunk_count=len(chunks),
    )


def register_memory_knowledge_source(
    uow: Stage06PlatformUnitOfWork,
    memory_item_id: UUID,
    *,
    actor: Actor,
    now: datetime,
    trace_id: str,
) -> KnowledgeSourceRegistration | None:
    if not _valid_trace_id(trace_id):
        return None
    projection = read_memory_projection(
        uow,
        memory_item_id,
        actor=actor,
        now=now,
        lifecycle_mode="read_only",
    )
    if not _valid_memory_projection_shape(projection, memory_item_id):
        return None

    item = uow.get_memory_item(memory_item_id)
    if item is None or _memory_metadata_is_group_or_telegram(item):
        return None

    scope = projection["scope"]
    payload = projection["payload"]
    if not _valid_memory_scope(scope, item.workspace_id):
        return None
    if not isinstance(payload, dict) or _contains_forbidden_projection_carrier(payload):
        return None

    memory_type = projection["memory_type"]
    content_version = projection["version"]
    if not isinstance(memory_type, str) or not memory_type.strip():
        return None
    if (
        not isinstance(content_version, int)
        or isinstance(content_version, bool)
        or content_version < 1
        or getattr(item, "version", None) != content_version
    ):
        return None

    try:
        projection_text = canonicalize_knowledge_text(
            json.dumps(
                {"memory_type": memory_type, "payload": payload},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError):
        return None

    root_memory_item_id = _resolve_memory_lineage_root(uow, item)
    if root_memory_item_id is None:
        return None
    logical_fingerprint = _sha256(f"memory_lineage:{root_memory_item_id}")
    projection_hash = _sha256(projection_text)
    source_projection = KnowledgeSourceProjection(
        source_type="memory_item",
        status="active",
        source_ref={
            "memory_item_id": str(memory_item_id),
            "memory_item_version": content_version,
        },
        scope=dict(scope),
        logical_source_fingerprint=logical_fingerprint,
        projection_hash=projection_hash,
        projection_text=projection_text,
        content_version=content_version,
    )

    related_sources = [
        source
        for source in uow.list_knowledge_sources(item.workspace_id)
        if source.source_type == "memory_item"
        and source.logical_source_fingerprint == logical_fingerprint
    ]
    same_version = [
        source
        for source in related_sources
        if source.content_version == content_version
    ]
    if same_version:
        existing = same_version[0]
        if (
            len(same_version) != 1
            or existing.projection_hash != projection_hash
            or existing.workspace_id != item.workspace_id
        ):
            return None
        event = _get_or_create_reference_event(
            uow,
            source=existing,
            event_type=_INDEX_EVENT_TYPE,
            trace_id=trace_id,
            now=now,
        )
        if event is None:
            return None
        return KnowledgeSourceRegistration(source=existing, event=event)

    if related_sources and content_version <= max(
        source.content_version for source in related_sources
    ):
        return None

    previous = max(
        (
            source
            for source in related_sources
            if source.status in {"active", "pending"}
        ),
        key=lambda source: (source.content_version, str(source.id)),
        default=None,
    )
    source = Stage08KnowledgeSource(
        id=uuid4(),
        workspace_id=item.workspace_id,
        source_type=source_projection.source_type,
        status=source_projection.status,
        source_ref=source_projection.source_ref,
        scope=source_projection.scope,
        logical_source_fingerprint=source_projection.logical_source_fingerprint,
        projection_hash=source_projection.projection_hash,
        projection_text=source_projection.projection_text,
        content_version=source_projection.content_version,
        supersedes_id=previous.id if previous is not None else None,
        valid_until=projection["valid_until"],
        created_at=now,
        updated_at=now,
    )
    event = _build_reference_event(
        source=source,
        event_type=_INDEX_EVENT_TYPE,
        trace_id=trace_id,
        now=now,
    )

    if previous is not None:
        locked_previous = uow.lock_knowledge_source_for_lifecycle(previous.id)
        if (
            locked_previous is None
            or locked_previous.workspace_id != item.workspace_id
            or locked_previous.logical_source_fingerprint != logical_fingerprint
            or locked_previous.status not in {"active", "pending"}
        ):
            return None
        locked_previous.status = "replaced"
        _mark_source_chunks_stale(uow, locked_previous)
        cleanup_event = _get_or_create_reference_event(
            uow,
            source=locked_previous,
            event_type=_CLEANUP_EVENT_TYPE,
            trace_id=(
                "source-replaced:"
                f"{locked_previous.id}:"
                f"{locked_previous.content_version}:"
                f"{locked_previous.projection_hash}"
            ),
            now=now,
        )
        if cleanup_event is None:
            return None
    uow.add_knowledge_source(source)
    uow.add_outbox_event(event)
    return KnowledgeSourceRegistration(source=source, event=event)


def revoke_knowledge_source(
    uow: Stage06PlatformUnitOfWork,
    source_id: UUID,
    *,
    now: datetime,
    reason_code: str,
) -> KnowledgeSourceLifecycleResult | None:
    if not isinstance(reason_code, str) or _SAFE_REASON_CODE.fullmatch(reason_code) is None:
        return None
    source = uow.lock_knowledge_source_for_lifecycle(source_id)
    if source is None or source.status not in {"active", "pending"}:
        return None

    source.status = "revoked"
    source.projection_text = None
    source.revoked_at = now
    _mark_source_chunks_stale(uow, source)
    trace_reference = "stage08:knowledge:cleanup:" + _sha256(
        f"{source.id}:{source.content_version}:{source.projection_hash}"
    )[:32]
    event = _get_or_create_reference_event(
        uow,
        source=source,
        event_type=_CLEANUP_EVENT_TYPE,
        trace_id=trace_reference,
        now=now,
    )
    if event is None:
        return None
    return KnowledgeSourceLifecycleResult(source=source, event=event)


def _valid_memory_projection_shape(
    projection: object,
    memory_item_id: UUID,
) -> bool:
    return (
        isinstance(projection, dict)
        and set(projection) == _MEMORY_PROJECTION_KEYS
        and projection.get("id") == memory_item_id
    )


def _valid_reindex_idempotency_key(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == value.strip()
        and len(value) <= 160
        and "\r" not in value
        and "\n" not in value
    )


def _actor_has_current_reindex_authority(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
    actor: Actor,
) -> bool:
    if (
        not isinstance(actor, Actor)
        or actor.actor_type != "user"
        or actor.role not in {"owner", "admin"}
        or not action_allowed_for_role(actor.role, "member.manage")
    ):
        return False
    matches = [
        member
        for member in _current_reindex_members(uow, workspace_id)
        if member.user_id == actor.actor_id
        and member.status == "active"
        and member.role == actor.role
    ]
    return len(matches) == 1


def _fresh_reindex_one(
    uow: SqlAlchemyStage06PlatformUnitOfWork,
    statement: object,
) -> object | None:
    with uow.session.no_autoflush:
        refreshed = statement.execution_options(  # type: ignore[attr-defined]
            populate_existing=True,
            autoflush=False,
        )
        rows = tuple(uow.session.scalars(refreshed))
    return rows[0] if len(rows) == 1 else None


def _lock_current_reindex_workspace(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
) -> Workspace | None:
    if not isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        return uow.lock_workspace_for_stage08_execution(workspace_id)
    try:
        workspace = _fresh_reindex_one(
            uow,
            select(Workspace).where(Workspace.id == workspace_id).with_for_update(),
        )
    except Exception:
        return None
    return workspace if isinstance(workspace, Workspace) else None


def _lock_current_reindex_source(
    uow: Stage06PlatformUnitOfWork,
    source_id: UUID,
) -> Stage08KnowledgeSource | None:
    if not isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        return uow.lock_knowledge_source_for_lifecycle(source_id)
    try:
        source = _fresh_reindex_one(
            uow,
            select(Stage08KnowledgeSource)
            .where(Stage08KnowledgeSource.id == source_id)
            .with_for_update(),
        )
    except Exception:
        return None
    return source if isinstance(source, Stage08KnowledgeSource) else None


def _current_reindex_members(
    uow: Stage06PlatformUnitOfWork,
    workspace_id: UUID,
) -> tuple[WorkspaceMember, ...]:
    if not isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        return tuple(uow.list_workspace_members(workspace_id))
    try:
        with uow.session.no_autoflush:
            statement = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id
            ).execution_options(populate_existing=True, autoflush=False)
            return tuple(uow.session.scalars(statement))
    except Exception:
        return ()


def _current_reindex_memory_item(
    uow: Stage06PlatformUnitOfWork,
    item_id: UUID,
) -> Stage08MemoryItem | None:
    if not isinstance(uow, SqlAlchemyStage06PlatformUnitOfWork):
        item = uow.get_memory_item(item_id)
        return item if isinstance(item, Stage08MemoryItem) else None
    try:
        item = _fresh_reindex_one(
            uow,
            select(Stage08MemoryItem).where(Stage08MemoryItem.id == item_id),
        )
    except Exception:
        return None
    return item if isinstance(item, Stage08MemoryItem) else None


def _resolve_current_reindex_memory_root(
    uow: Stage06PlatformUnitOfWork,
    item_id: UUID,
    workspace_id: UUID,
) -> UUID | None:
    current = _current_reindex_memory_item(uow, item_id)
    current_identity = _validated_memory_lineage_identity(current, workspace_id)
    if (
        current is None
        or current.id != item_id
        or current.workspace_id != workspace_id
        or current.status != "active"
        or current.revoked_at is not None
        or current.deleted_at is not None
        or not _positive_version(current.version)
        or current_identity is None
        or not _valid_lineage_source_refs(current)
    ):
        return None
    seen = {current.id}
    while current.supersedes_id is not None:
        predecessor_id = current.supersedes_id
        if not isinstance(predecessor_id, UUID) or predecessor_id in seen:
            return None
        predecessor = _current_reindex_memory_item(uow, predecessor_id)
        if (
            predecessor is None
            or predecessor.id != predecessor_id
            or predecessor.workspace_id != workspace_id
            or predecessor.status != "superseded"
            or predecessor.revoked_at is not None
            or predecessor.deleted_at is not None
            or not _positive_version(predecessor.version)
            or predecessor.version >= current.version
            or _validated_memory_lineage_identity(predecessor, workspace_id)
            != current_identity
            or not _valid_lineage_source_refs(predecessor)
        ):
            return None
        seen.add(predecessor_id)
        current = predecessor
    return current.id


def _memory_source_is_reindexable(
    uow: Stage06PlatformUnitOfWork,
    source: Stage08KnowledgeSource,
    *,
    actor: Actor,
    now: datetime,
) -> bool:
    if (
        source.source_type != "memory_item"
        or source.status != "active"
        or source.revoked_at is not None
        or source.deleted_at is not None
        or not isinstance(source.projection_text, str)
        or not source.projection_text.strip()
    ):
        return False
    if source.valid_until is not None:
        try:
            if source.valid_until <= now:
                return False
        except TypeError:
            return False
    if not isinstance(source.source_ref, dict) or set(source.source_ref) != {
        "memory_item_id",
        "memory_item_version",
    }:
        return False
    memory_item_id = _canonical_uuid(source.source_ref.get("memory_item_id"))
    memory_item_version = source.source_ref.get("memory_item_version")
    if memory_item_id is None or not _positive_version(memory_item_version):
        return False

    item = _current_reindex_memory_item(uow, memory_item_id)
    if (
        item is None
        or item.status != "active"
        or item.revoked_at is not None
        or item.deleted_at is not None
        or _memory_metadata_is_group_or_telegram(item)
    ):
        return False
    projection = read_memory_projection(
        uow,
        memory_item_id,
        actor=actor,
        now=now,
        lifecycle_mode="read_only",
    )
    if not _valid_memory_projection_shape(projection, memory_item_id):
        return False
    if (
        item.workspace_id != source.workspace_id
        or item.version != memory_item_version
        or projection.get("version") != source.content_version
        or source.content_version != memory_item_version
        or projection.get("valid_until") != source.valid_until
        or projection.get("scope") != source.scope
        or not _valid_memory_scope(projection.get("scope"), source.workspace_id)
    ):
        return False
    payload = projection.get("payload")
    memory_type = projection.get("memory_type")
    if (
        not isinstance(payload, dict)
        or _contains_forbidden_projection_carrier(payload)
        or not isinstance(memory_type, str)
        or not memory_type.strip()
    ):
        return False
    try:
        projection_text = canonicalize_knowledge_text(
            json.dumps(
                {"memory_type": memory_type, "payload": payload},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    except (TypeError, ValueError):
        return False
    root_id = _resolve_current_reindex_memory_root(
        uow,
        memory_item_id,
        source.workspace_id,
    )
    return (
        root_id is not None
        and source.logical_source_fingerprint
        == _sha256(f"memory_lineage:{root_id}")
        and source.projection_text == projection_text
        and source.projection_hash == _sha256(projection_text)
    )


def _reindex_receipt_from_replay(
    uow: Stage06PlatformUnitOfWork,
    source: Stage08KnowledgeSource,
    response_ref: object,
) -> KnowledgeReindexReceipt:
    if not isinstance(response_ref, dict) or set(response_ref) != {
        "ticket_id",
        "status",
    }:
        raise PlatformValidationError(
            "knowledge_reindex_replay_invalid",
            "knowledge_reindex_replay_invalid",
        )
    ticket_id = _canonical_uuid(response_ref.get("ticket_id"))
    if ticket_id is None or response_ref.get("status") != "accepted":
        raise PlatformValidationError(
            "knowledge_reindex_replay_invalid",
            "knowledge_reindex_replay_invalid",
        )
    event = uow.get_outbox_event(ticket_id)
    reference = _validate_reference_event(event, _INDEX_EVENT_TYPE)
    if (
        reference is None
        or reference[0] != source.workspace_id
        or reference[1] != source.id
        or reference[2] != source.content_version
        or reference[3] != source.projection_hash
    ):
        raise PlatformValidationError(
            "knowledge_reindex_replay_invalid",
            "knowledge_reindex_replay_invalid",
        )
    return KnowledgeReindexReceipt(ticket_id=ticket_id)


def _discard_reindex_idempotency_reservation(
    uow: Stage06PlatformUnitOfWork,
    record: object,
) -> None:
    records = getattr(uow, "idempotency_records", None)
    if isinstance(records, list) and record in records:
        records.remove(record)


def _valid_memory_scope(scope: object, workspace_id: UUID) -> bool:
    if not isinstance(scope, dict) or not scope or not set(scope).issubset(
        _MEMORY_SCOPE_KEYS
    ):
        return False
    try:
        if UUID(str(scope.get("workspace_id"))) != workspace_id:
            return False
        for key, value in scope.items():
            if key != "workspace_id" and value is not None:
                UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _resolve_memory_lineage_root(
    uow: Stage06PlatformUnitOfWork,
    item: object,
) -> UUID | None:
    current_id = getattr(item, "id", None)
    workspace_id = getattr(item, "workspace_id", None)
    current_version = getattr(item, "version", None)
    current_identity = _validated_memory_lineage_identity(item, workspace_id)
    if (
        not isinstance(current_id, UUID)
        or not isinstance(workspace_id, UUID)
        or not _positive_version(current_version)
        or getattr(item, "status", None) != "active"
        or current_identity is None
        or not _valid_lineage_source_refs(item)
    ):
        return None

    seen = {current_id}
    current = item
    while getattr(current, "supersedes_id", None) is not None:
        predecessor_id = getattr(current, "supersedes_id", None)
        if not isinstance(predecessor_id, UUID) or predecessor_id in seen:
            return None
        predecessor = uow.get_memory_item(predecessor_id)
        predecessor_identity = _validated_memory_lineage_identity(
            predecessor,
            workspace_id,
        )
        if (
            predecessor is None
            or getattr(predecessor, "id", None) != predecessor_id
            or getattr(predecessor, "workspace_id", None) != workspace_id
            or getattr(predecessor, "status", None) != "superseded"
            or not _positive_version(getattr(predecessor, "version", None))
            or getattr(predecessor, "version", None)
            >= getattr(current, "version", None)
            or predecessor_identity != current_identity
            or not _valid_lineage_source_refs(predecessor)
        ):
            return None
        seen.add(predecessor_id)
        current = predecessor
    return getattr(current, "id", None)


def _validated_memory_lineage_identity(
    item: object,
    workspace_id: object,
) -> tuple[str, str] | None:
    memory_type = getattr(item, "memory_type", None)
    scope = getattr(item, "scope", None)
    if not isinstance(memory_type, str) or not memory_type.strip():
        return None
    try:
        projection = MemoryScopeProjection.model_validate(scope)
    except (TypeError, ValueError):
        return None
    if projection.workspace_id != workspace_id or projection.group_chat_ref is not None:
        return None
    canonical_scope = json.dumps(
        projection.model_dump(mode="json", exclude_none=False),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return memory_type, canonical_scope


def _valid_lineage_source_refs(item: object) -> bool:
    source_refs = getattr(item, "source_refs", None)
    if not isinstance(source_refs, list) or not source_refs:
        return False
    try:
        projections = tuple(
            MemorySourceRef.model_validate(source_ref)
            for source_ref in source_refs
        )
    except (TypeError, ValueError):
        return False
    return all(
        projection.source_kind in {"platform_record", "record_change_draft"}
        for projection in projections
    )


def _positive_version(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _memory_metadata_is_group_or_telegram(item: object) -> bool:
    scope = getattr(item, "scope", None)
    if isinstance(scope, dict) and scope.get("group_chat_ref") is not None:
        return True
    source_refs = getattr(item, "source_refs", None)
    if not isinstance(source_refs, list):
        return True
    for source_ref in source_refs:
        if not isinstance(source_ref, dict):
            return True
        source_kind = source_ref.get("source_kind")
        if not isinstance(source_kind, str):
            return True
        normalized_kind = source_kind.casefold()
        if "telegram" in normalized_kind or "group" in normalized_kind:
            return True
    return False


def _contains_forbidden_projection_carrier(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                return True
            normalized_key = key.casefold()
            if (
                normalized_key in _FORBIDDEN_PROJECTION_KEYS
                or "telegram" in normalized_key
            ):
                return True
            if _contains_forbidden_projection_carrier(item):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_projection_carrier(item) for item in value)
    return isinstance(value, str) and value.startswith("stage06-binding:")


def _mark_source_chunks_stale(
    uow: Stage06PlatformUnitOfWork,
    source: Stage08KnowledgeSource,
) -> None:
    for chunk in uow.list_knowledge_chunks(source.id, source.content_version):
        if chunk.status not in {"stale", "deleted"}:
            chunk.status = "stale"


def _validate_reference_event(
    event: object,
    expected_event_type: str,
) -> tuple[UUID, UUID, int, str] | None:
    if not isinstance(event, OutboxEvent):
        return None
    payload = event.payload
    if (
        event.event_type != expected_event_type
        or event.aggregate_type != "stage08_knowledge_source"
        or event.status not in {"pending", "processed"}
        or not isinstance(payload, dict)
        or set(payload) != _REFERENCE_PAYLOAD_KEYS
        or not _is_trace_ref(event.trace_id)
        or payload.get("trace_id") != event.trace_id
    ):
        return None
    workspace_id = _canonical_uuid(payload.get("workspace_id"))
    source_id = _canonical_uuid(payload.get("knowledge_source_id"))
    content_version = payload.get("content_version")
    projection_hash = payload.get("projection_hash")
    if (
        workspace_id is None
        or source_id is None
        or event.aggregate_id != str(source_id)
        or not _positive_version(content_version)
        or not isinstance(projection_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", projection_hash) is None
    ):
        return None
    return workspace_id, source_id, content_version, projection_hash


def _source_matches_index_reference(
    source: Stage08KnowledgeSource | None,
    *,
    workspace_id: UUID,
    content_version: int,
    projection_hash: str,
    now: datetime,
) -> bool:
    if (
        source is None
        or source.workspace_id != workspace_id
        or source.content_version != content_version
        or source.projection_hash != projection_hash
        or source.status != "active"
        or not isinstance(source.projection_text, str)
        or not source.projection_text.strip()
    ):
        return False
    if source.valid_until is None:
        return True
    try:
        return source.valid_until > now
    except TypeError:
        return False


def _source_matches_cleanup_reference(
    source: Stage08KnowledgeSource | None,
    *,
    workspace_id: UUID,
    content_version: int,
    projection_hash: str,
) -> bool:
    return bool(
        source is not None
        and source.workspace_id == workspace_id
        and source.content_version == content_version
        and source.projection_hash == projection_hash
        and source.status in {"replaced", "revoked", "expired", "deleted"}
    )


def _valid_embedding_provider_profile(provider: object) -> bool:
    try:
        return (
            type(provider.profile) is str
            and provider.profile == TEST_EMBEDDING_PROFILE
            and type(provider.version) is int
            and provider.version == TEST_EMBEDDING_VERSION
            and type(provider.dimension) is int
            and provider.dimension == TEST_EMBEDDING_DIMENSION
        )
    except Exception:
        return False


def _validated_embeddings(
    embeddings: object,
    expected_count: int,
) -> tuple[tuple[float, ...], ...] | None:
    try:
        if not isinstance(embeddings, tuple) or len(embeddings) != expected_count:
            return None
        validated: list[tuple[float, ...]] = []
        for embedding in embeddings:
            if (
                not isinstance(embedding, tuple)
                or len(embedding) != TEST_EMBEDDING_DIMENSION
            ):
                return None
            values: list[float] = []
            for value in embedding:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    return None
                converted = float(value)
                if not math.isfinite(converted):
                    return None
                values.append(converted)
            validated.append(tuple(values))
        return tuple(validated)
    except Exception:
        return None


def _existing_index_matches(
    source: Stage08KnowledgeSource,
    chunks: list[Stage08KnowledgeChunk],
    projections: tuple[object, ...],
) -> bool:
    try:
        if len(chunks) != len(projections):
            return False
        for chunk, projection in zip(chunks, projections, strict=True):
            expected_embedding = deterministic_test_hash_embedding(
                TEST_EMBEDDING_PROFILE,
                projection.chunk_text or "",
            )
            if (
                chunk.workspace_id != source.workspace_id
                or chunk.source_id != source.id
                or chunk.source_version != source.content_version
                or chunk.status != "indexed"
                or chunk.ordinal != projection.ordinal
                or chunk.chunk_text != projection.chunk_text
                or chunk.chunk_hash != projection.chunk_hash
                or tuple(chunk.keyword_terms) != projection.keyword_terms
                or chunk.embedding_profile != TEST_EMBEDDING_PROFILE
                or chunk.embedding_version != TEST_EMBEDDING_VERSION
                or _validated_single_embedding(chunk.embedding) != expected_embedding
            ):
                return False
        return True
    except Exception:
        return False


def _validated_single_embedding(value: object) -> tuple[float, ...] | None:
    try:
        candidate = tuple(float(item) for item in value)
    except Exception:
        return None
    validated = _validated_embeddings((candidate,), 1)
    return None if validated is None else validated[0]


def _scrub_conflicting_chunks(
    source: Stage08KnowledgeSource,
    chunks: list[Stage08KnowledgeChunk],
    now: datetime,
) -> None:
    for chunk in chunks:
        if (
            chunk.workspace_id != source.workspace_id
            or chunk.source_id != source.id
            or chunk.source_version != source.content_version
            or chunk.status == "deleted"
        ):
            continue
        chunk.chunk_text = None
        chunk.keyword_terms = []
        chunk.embedding = None
        chunk.embedding_profile = None
        chunk.embedding_version = None
        chunk.status = "stale"
        chunk.updated_at = now


def _mark_event_processed(event: OutboxEvent, now: datetime) -> None:
    if event.status != "processed":
        event.status = "processed"
        event.processed_at = now
    event.last_error = None
    event.last_error_redacted = None


def _canonical_uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    return parsed if str(parsed) == value else None


def _get_or_create_reference_event(
    uow: Stage06PlatformUnitOfWork,
    *,
    source: Stage08KnowledgeSource,
    event_type: str,
    trace_id: str,
    now: datetime,
) -> OutboxEvent | None:
    expected = _build_reference_event(
        source=source,
        event_type=event_type,
        trace_id=trace_id,
        now=now,
    )
    existing = uow.get_outbox_event_by_idempotency_key(expected.idempotency_key)
    if existing is not None:
        if (
            existing.event_type != expected.event_type
            or existing.aggregate_type != expected.aggregate_type
            or existing.aggregate_id != expected.aggregate_id
            or not isinstance(existing.payload, dict)
            or set(existing.payload) != _REFERENCE_PAYLOAD_KEYS
            or existing.payload["workspace_id"] != expected.payload["workspace_id"]
            or existing.payload["knowledge_source_id"]
            != expected.payload["knowledge_source_id"]
            or existing.payload["content_version"]
            != expected.payload["content_version"]
            or existing.payload["projection_hash"]
            != expected.payload["projection_hash"]
            or existing.payload["trace_id"] != existing.trace_id
            or not _is_trace_ref(existing.trace_id)
        ):
            return None
        return existing
    uow.add_outbox_event(expected)
    return expected


def _build_reference_event(
    *,
    source: Stage08KnowledgeSource,
    event_type: str,
    trace_id: str,
    now: datetime,
) -> OutboxEvent:
    trace_ref = _derive_trace_ref(trace_id)
    event_kind = "index" if event_type == _INDEX_EVENT_TYPE else "cleanup"
    idempotency_key = f"stage08:knowledge:{event_kind}:" + _sha256(
        ":".join(
            (
                source.logical_source_fingerprint,
                str(source.content_version),
                source.projection_hash,
            )
        )
    )
    payload = {
        "workspace_id": str(source.workspace_id),
        "knowledge_source_id": str(source.id),
        "content_version": source.content_version,
        "projection_hash": source.projection_hash,
        "trace_id": trace_ref,
    }
    return OutboxEvent(
        id=uuid4(),
        event_type=event_type,
        aggregate_type="stage08_knowledge_source",
        aggregate_id=str(source.id),
        payload=payload,
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        trace_id=trace_ref,
        created_at=now,
    )


def _valid_trace_id(trace_id: object) -> bool:
    return (
        isinstance(trace_id, str)
        and bool(trace_id.strip())
        and len(trace_id) <= 120
        and "\r" not in trace_id
        and "\n" not in trace_id
    )


def _derive_trace_ref(caller_trace_id: str) -> str:
    return _sha256(f"stage08-knowledge-trace-v1:{caller_trace_id}")


def _is_trace_ref(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
