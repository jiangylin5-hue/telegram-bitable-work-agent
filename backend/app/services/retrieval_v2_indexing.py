"""Stage12-D reference-only projection events and atomic index lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.outbox import OutboxEvent
from app.models.stage12_retrieval import (
    Stage12RelationEdge,
    Stage12RetrievalChunk,
    Stage12RetrievalProfile,
    Stage12RetrievalScopeRegistration,
    Stage12RetrievalSource,
)
from app.schemas.retrieval_v2 import (
    EmbeddingProfileV1,
    RetrievalChunkV2,
    RetrievalProjectionV2,
)
from app.services.retrieval_v2_embeddings import (
    EmbeddingProviderError,
    validate_embedding_batch,
)
from app.services.retrieval_v2_projection import TokenCounter, chunk_projection


_REQUEST_EVENT = "stage12.retrieval_projection.requested"
_REVOKE_EVENT = "stage12.retrieval_projection.revoked"
_SOURCE_CHANGE_EVENT = "stage12.retrieval_source.changed"
_SCOPE_BOOTSTRAP_EVENT = "stage12.retrieval_scope.bootstrap_requested"
_SELECTED_PROFILE = "stage12.openrouter-bge-m3-v1"
_SELECTED_REVISION = "baai/bge-m3-20251117"
_REQUEST_KEYS = frozenset(
    {
        "workspace_id",
        "base_id",
        "table_id",
        "record_id",
        "source_type",
        "source_id",
        "source_version",
        "content_hash",
        "visibility_profile_hash",
        "scope_hash",
        "trace_id",
    }
)
_SOURCE_CHANGE_KEYS = frozenset(
    {
        "workspace_id",
        "base_id",
        "table_id",
        "record_id",
        "source_type",
        "source_id",
        "source_version",
        "mutation_kind",
        "trace_id",
    }
)
_SOURCE_CHANGE_KINDS = frozenset(
    {
        "record_changed",
        "schema_changed",
        "link_changed",
        "permission_changed",
        "scope_changed",
        "profile_changed",
        "deleted",
    }
)
_BOOTSTRAP_PAGE_SIZE_MAX = 200
_SAFE_REASON = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


class EmbeddingDocumentProvider(Protocol):
    profile: EmbeddingProfileV1

    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]: ...


ProjectionReader = Callable[
    [dict[str, object]],
    RetrievalProjectionV2 | None,
]


@dataclass(frozen=True, slots=True)
class RetrievalIndexingResult:
    status: str
    source_version: int | None = None
    indexed_chunk_count: int = 0
    reused_embedding: bool = False
    error_code: str = "none"


@dataclass(frozen=True, slots=True)
class RetrievalSourceExpansionResult:
    status: str
    requested_projection_count: int = 0
    error_code: str = "none"


@dataclass(frozen=True, slots=True)
class RetrievalRevocationResult:
    revoked_source_count: int
    revoked_chunk_count: int
    event: OutboxEvent


@dataclass(frozen=True, slots=True)
class RetrievalProfileRollbackResult:
    status: str
    reactivated_source_count: int


class RetrievalIndexUnitOfWork(Protocol):
    def get_outbox_event_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> OutboxEvent | None: ...

    def add_outbox_event(self, event: OutboxEvent) -> None: ...

    def get_profile(self, profile_name: str) -> Stage12RetrievalProfile | None: ...

    def list_profiles(self) -> list[Stage12RetrievalProfile]: ...

    def list_sources(
        self,
        *,
        workspace_id: UUID | None = None,
        source_type: str | None = None,
        source_identity: str | None = None,
        visibility_profile_hash: str | None = None,
        embedding_profile: str | None = None,
    ) -> list[Stage12RetrievalSource]: ...

    def list_chunks(self, source_id: UUID) -> list[Stage12RetrievalChunk]: ...

    def list_registrations(
        self,
        *,
        workspace_id: UUID | None = None,
    ) -> list[Stage12RetrievalScopeRegistration]: ...

    def list_relation_edges(
        self,
        *,
        workspace_id: UUID | None = None,
        scope_hash: str | None = None,
    ) -> list[Stage12RelationEdge]: ...

    def add_source(self, source: Stage12RetrievalSource) -> None: ...

    def add_chunk(self, chunk: Stage12RetrievalChunk) -> None: ...

    def add_registration(
        self,
        registration: Stage12RetrievalScopeRegistration,
    ) -> None: ...

    def add_relation_edge(self, edge: Stage12RelationEdge) -> None: ...

    def flush(self) -> None: ...

    @contextmanager
    def atomic(self) -> Iterator[None]: ...


class MemoryRetrievalIndexUnitOfWork:
    def __init__(self) -> None:
        self.profiles: list[Stage12RetrievalProfile] = []
        self.sources: list[Stage12RetrievalSource] = []
        self.chunks: list[Stage12RetrievalChunk] = []
        self.relation_edges: list[Stage12RelationEdge] = []
        self.registrations: list[Stage12RetrievalScopeRegistration] = []
        self.outbox_events: list[OutboxEvent] = []

    def get_outbox_event_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> OutboxEvent | None:
        return next(
            (
                event
                for event in self.outbox_events
                if event.idempotency_key == idempotency_key
            ),
            None,
        )

    def add_outbox_event(self, event: OutboxEvent) -> None:
        self.outbox_events.append(event)

    def get_profile(self, profile_name: str) -> Stage12RetrievalProfile | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.profile_name == profile_name
            ),
            None,
        )

    def list_profiles(self) -> list[Stage12RetrievalProfile]:
        return list(self.profiles)

    def list_sources(
        self,
        *,
        workspace_id: UUID | None = None,
        source_type: str | None = None,
        source_identity: str | None = None,
        visibility_profile_hash: str | None = None,
        embedding_profile: str | None = None,
    ) -> list[Stage12RetrievalSource]:
        return [
            source
            for source in self.sources
            if (workspace_id is None or source.workspace_id == workspace_id)
            and (source_type is None or source.source_type == source_type)
            and (source_identity is None or source.source_identity == source_identity)
            and (
                visibility_profile_hash is None
                or source.visibility_profile_hash == visibility_profile_hash
            )
            and (
                embedding_profile is None
                or source.embedding_profile == embedding_profile
            )
        ]

    def list_chunks(self, source_id: UUID) -> list[Stage12RetrievalChunk]:
        return [chunk for chunk in self.chunks if chunk.source_id == source_id]

    def list_registrations(
        self,
        *,
        workspace_id: UUID | None = None,
    ) -> list[Stage12RetrievalScopeRegistration]:
        return [
            registration
            for registration in self.registrations
            if workspace_id is None or registration.workspace_id == workspace_id
        ]

    def list_relation_edges(
        self,
        *,
        workspace_id: UUID | None = None,
        scope_hash: str | None = None,
    ) -> list[Stage12RelationEdge]:
        return [
            edge
            for edge in self.relation_edges
            if (workspace_id is None or edge.workspace_id == workspace_id)
            and (scope_hash is None or edge.scope_hash == scope_hash)
        ]

    def add_source(self, source: Stage12RetrievalSource) -> None:
        self.sources.append(source)

    def add_chunk(self, chunk: Stage12RetrievalChunk) -> None:
        self.chunks.append(chunk)

    def add_registration(
        self,
        registration: Stage12RetrievalScopeRegistration,
    ) -> None:
        self.registrations.append(registration)

    def add_relation_edge(self, edge: Stage12RelationEdge) -> None:
        self.relation_edges.append(edge)

    def flush(self) -> None:
        return None

    @contextmanager
    def atomic(self) -> Iterator[None]:
        source_length = len(self.sources)
        chunk_length = len(self.chunks)
        registration_length = len(self.registrations)
        relation_edge_length = len(self.relation_edges)
        outbox_length = len(self.outbox_events)
        profile_states = {
            profile.id: (
                profile.status,
                profile.activated_at,
                profile.retired_at,
            )
            for profile in self.profiles
        }
        source_states = {
            source.id: (
                source.status,
                source.is_active,
                source.activated_at,
                source.revoked_at,
            )
            for source in self.sources
        }
        chunk_states = {
            chunk.id: (chunk.status, chunk.revoked_at) for chunk in self.chunks
        }
        registration_states = {
            registration.id: (
                registration.status,
                registration.last_seen_at,
                registration.expires_at,
                registration.revoked_at,
            )
            for registration in self.registrations
        }
        relation_edge_states = {
            edge.id: (edge.status, edge.revoked_at) for edge in self.relation_edges
        }
        outbox_states = {
            event.id: (
                event.status,
                event.processed_at,
                event.last_error,
                event.last_error_redacted,
            )
            for event in self.outbox_events
        }
        try:
            yield
        except Exception:
            del self.sources[source_length:]
            del self.chunks[chunk_length:]
            del self.registrations[registration_length:]
            del self.relation_edges[relation_edge_length:]
            del self.outbox_events[outbox_length:]
            for profile in self.profiles:
                state = profile_states[profile.id]
                (
                    profile.status,
                    profile.activated_at,
                    profile.retired_at,
                ) = state
            for source in self.sources:
                state = source_states[source.id]
                (
                    source.status,
                    source.is_active,
                    source.activated_at,
                    source.revoked_at,
                ) = state
            for chunk in self.chunks:
                chunk.status, chunk.revoked_at = chunk_states[chunk.id]
            for registration in self.registrations:
                (
                    registration.status,
                    registration.last_seen_at,
                    registration.expires_at,
                    registration.revoked_at,
                ) = registration_states[registration.id]
            for edge in self.relation_edges:
                edge.status, edge.revoked_at = relation_edge_states[edge.id]
            for event in self.outbox_events:
                state = outbox_states[event.id]
                (
                    event.status,
                    event.processed_at,
                    event.last_error,
                    event.last_error_redacted,
                ) = state
            raise


class SqlAlchemyRetrievalIndexUnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_outbox_event_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> OutboxEvent | None:
        return self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.idempotency_key == idempotency_key)
        )

    def add_outbox_event(self, event: OutboxEvent) -> None:
        self.session.add(event)

    def get_profile(self, profile_name: str) -> Stage12RetrievalProfile | None:
        return self.session.scalar(
            select(Stage12RetrievalProfile).where(
                Stage12RetrievalProfile.profile_name == profile_name
            )
        )

    def list_profiles(self) -> list[Stage12RetrievalProfile]:
        return list(self.session.scalars(select(Stage12RetrievalProfile)))

    def list_sources(
        self,
        *,
        workspace_id: UUID | None = None,
        source_type: str | None = None,
        source_identity: str | None = None,
        visibility_profile_hash: str | None = None,
        embedding_profile: str | None = None,
    ) -> list[Stage12RetrievalSource]:
        statement = select(Stage12RetrievalSource)
        if workspace_id is not None:
            statement = statement.where(
                Stage12RetrievalSource.workspace_id == workspace_id
            )
        if source_type is not None:
            statement = statement.where(
                Stage12RetrievalSource.source_type == source_type
            )
        if source_identity is not None:
            statement = statement.where(
                Stage12RetrievalSource.source_identity == source_identity
            )
        if visibility_profile_hash is not None:
            statement = statement.where(
                Stage12RetrievalSource.visibility_profile_hash
                == visibility_profile_hash
            )
        if embedding_profile is not None:
            statement = statement.where(
                Stage12RetrievalSource.embedding_profile == embedding_profile
            )
        return list(
            self.session.scalars(
                statement.order_by(Stage12RetrievalSource.source_version)
            )
        )

    def list_chunks(self, source_id: UUID) -> list[Stage12RetrievalChunk]:
        return list(
            self.session.scalars(
                select(Stage12RetrievalChunk)
                .where(Stage12RetrievalChunk.source_id == source_id)
                .order_by(Stage12RetrievalChunk.ordinal)
            )
        )

    def list_registrations(
        self,
        *,
        workspace_id: UUID | None = None,
    ) -> list[Stage12RetrievalScopeRegistration]:
        statement = select(Stage12RetrievalScopeRegistration)
        if workspace_id is not None:
            statement = statement.where(
                Stage12RetrievalScopeRegistration.workspace_id == workspace_id
            )
        return list(
            self.session.scalars(
                statement.order_by(Stage12RetrievalScopeRegistration.created_at)
            )
        )

    def list_relation_edges(
        self,
        *,
        workspace_id: UUID | None = None,
        scope_hash: str | None = None,
    ) -> list[Stage12RelationEdge]:
        statement = select(Stage12RelationEdge)
        if workspace_id is not None:
            statement = statement.where(
                Stage12RelationEdge.workspace_id == workspace_id
            )
        if scope_hash is not None:
            statement = statement.where(Stage12RelationEdge.scope_hash == scope_hash)
        return list(self.session.scalars(statement.order_by(Stage12RelationEdge.id)))

    def add_source(self, source: Stage12RetrievalSource) -> None:
        self.session.add(source)

    def add_chunk(self, chunk: Stage12RetrievalChunk) -> None:
        self.session.add(chunk)

    def add_registration(
        self,
        registration: Stage12RetrievalScopeRegistration,
    ) -> None:
        self.session.add(registration)

    def add_relation_edge(self, edge: Stage12RelationEdge) -> None:
        self.session.add(edge)

    def flush(self) -> None:
        self.session.flush()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        with self.session.begin_nested():
            yield


def request_retrieval_source_change(
    uow: RetrievalIndexUnitOfWork,
    *,
    workspace_id: UUID,
    base_id: UUID,
    table_id: UUID,
    record_id: UUID | None,
    source_type: str,
    source_identity: str,
    source_version: int,
    mutation_kind: str,
    trace_id: str,
    now: datetime,
) -> OutboxEvent:
    if (
        source_type not in {"schema_table", "schema_field", "record", "record_field"}
        or not isinstance(source_identity, str)
        or not source_identity.strip()
        or source_identity != source_identity.strip()
        or len(source_identity) > 240
        or "\r" in source_identity
        or "\n" in source_identity
        or not isinstance(source_version, int)
        or isinstance(source_version, bool)
        or source_version < 1
        or mutation_kind not in _SOURCE_CHANGE_KINDS
        or (source_type in {"record", "record_field"}) != (record_id is not None)
        or not _valid_trace(trace_id)
    ):
        raise ValueError("retrieval_source_change_invalid")
    trace_ref = _sha256(f"stage12-retrieval-source-change-v1:{trace_id}")
    payload = {
        "workspace_id": str(workspace_id),
        "base_id": str(base_id),
        "table_id": str(table_id),
        "record_id": None if record_id is None else str(record_id),
        "source_type": source_type,
        "source_id": source_identity,
        "source_version": source_version,
        "mutation_kind": mutation_kind,
        "trace_id": trace_ref,
    }
    idempotency_key = "stage12:retrieval:source-change:" + _sha256(
        ":".join(
            (
                str(workspace_id),
                source_type,
                source_identity,
                str(source_version),
                mutation_kind,
            )
        )
    )
    expected = OutboxEvent(
        id=uuid4(),
        event_type=_SOURCE_CHANGE_EVENT,
        aggregate_type="stage12_retrieval_source",
        aggregate_id=source_identity,
        payload=payload,
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        trace_id=trace_ref,
        created_at=now,
    )
    existing = uow.get_outbox_event_by_idempotency_key(idempotency_key)
    if existing is not None:
        if not _events_equal(existing, expected):
            raise ValueError("retrieval_source_change_event_conflict")
        return existing
    uow.add_outbox_event(expected)
    return expected


def request_retrieval_scope_bootstrap(
    uow: RetrievalIndexUnitOfWork,
    *,
    workspace_id: UUID,
    registration_id: UUID,
    cursor: str | None,
    page_size: int,
    trace_id: str,
    now: datetime,
) -> OutboxEvent:
    if (
        (cursor is not None and not _valid_bootstrap_cursor(cursor))
        or isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= _BOOTSTRAP_PAGE_SIZE_MAX
        or not _valid_trace(trace_id)
        or now.tzinfo is None
    ):
        raise ValueError("retrieval_scope_bootstrap_invalid")
    trace_ref = _sha256(f"stage12-retrieval-bootstrap-v1:{trace_id}")
    payload = {
        "workspace_id": str(workspace_id),
        "registration_id": str(registration_id),
        "cursor": cursor,
        "page_size": page_size,
        "trace_id": trace_ref,
    }
    idempotency_key = "stage12:retrieval:bootstrap:" + _sha256(
        ":".join(
            (
                str(workspace_id),
                str(registration_id),
                cursor or "root",
                str(page_size),
            )
        )
    )
    expected = OutboxEvent(
        id=uuid4(),
        event_type=_SCOPE_BOOTSTRAP_EVENT,
        aggregate_type="stage12_retrieval_scope_registration",
        aggregate_id=str(registration_id),
        payload=payload,
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        trace_id=trace_ref,
        created_at=now,
    )
    existing = uow.get_outbox_event_by_idempotency_key(idempotency_key)
    if existing is not None:
        if not _events_equal(existing, expected):
            raise ValueError("retrieval_scope_bootstrap_event_conflict")
        return existing
    uow.add_outbox_event(expected)
    return expected


def expand_retrieval_source_change_event(
    uow: RetrievalIndexUnitOfWork,
    event: OutboxEvent,
    *,
    projection_reader: Callable[
        [dict[str, object]],
        tuple[RetrievalProjectionV2, ...],
    ],
    registered_scope_profiles: frozenset[tuple[str, str]],
    now: datetime,
) -> RetrievalSourceExpansionResult:
    reference = _source_change_reference(event)
    if reference is None:
        return RetrievalSourceExpansionResult(
            status="failed",
            error_code="retrieval_source_change_event_invalid",
        )
    if event.status == "processed":
        return RetrievalSourceExpansionResult(status="replayed")
    try:
        projections = projection_reader(dict(reference))
    except Exception:
        return RetrievalSourceExpansionResult(
            status="failed",
            error_code="retrieval_source_projection_read_failed",
        )
    if not isinstance(projections, tuple) or any(
        not isinstance(projection, RetrievalProjectionV2)
        or not _projection_matches_source_reference(projection, reference)
        for projection in projections
    ):
        return RetrievalSourceExpansionResult(
            status="failed",
            error_code="retrieval_source_projection_invalid",
        )
    if any(
        not isinstance(profile, tuple)
        or len(profile) != 2
        or not _hash(profile[0])
        or not _hash(profile[1])
        for profile in registered_scope_profiles
    ):
        return RetrievalSourceExpansionResult(
            status="failed",
            error_code="retrieval_source_scope_registry_invalid",
        )
    materialized_profiles = {
        (source.visibility_profile_hash, source.scope_hash)
        for source in uow.list_sources(
            workspace_id=UUID(str(reference["workspace_id"])),
            source_type=str(reference["source_type"]),
        )
        if source.status != "revoked"
        and _normalized_source_identity(source.source_identity)
        == _normalized_source_identity(str(reference["source_id"]))
    }
    allowed_profiles = set(registered_scope_profiles) | materialized_profiles
    if any(
        (projection.visibility_profile_hash, projection.scope_hash)
        not in allowed_profiles
        for projection in projections
    ):
        return RetrievalSourceExpansionResult(
            status="failed",
            error_code="retrieval_source_scope_unregistered",
        )
    unique = {
        (
            projection.visibility_profile_hash,
            projection.scope_hash,
            projection.content_hash,
        ): projection
        for projection in projections
    }
    ordered = tuple(unique[key] for key in sorted(unique))
    try:
        with uow.atomic():
            for projection in ordered:
                request_retrieval_projection(
                    uow,
                    projection,
                    trace_id=_sha256(
                        f"{event.trace_id}:{projection.visibility_profile_hash}:"
                        f"{projection.scope_hash}"
                    ),
                    now=now,
                )
            _mark_event_processed(event, now)
            uow.flush()
    except Exception:
        return RetrievalSourceExpansionResult(
            status="failed",
            error_code="retrieval_source_projection_enqueue_failed",
        )
    return RetrievalSourceExpansionResult(
        status="expanded" if ordered else "discarded",
        requested_projection_count=len(ordered),
    )


def request_retrieval_projection(
    uow: RetrievalIndexUnitOfWork,
    projection: RetrievalProjectionV2,
    *,
    trace_id: str,
    now: datetime,
) -> OutboxEvent:
    if not _valid_trace(trace_id):
        raise ValueError("retrieval_projection_trace_invalid")
    trace_ref = _sha256(f"stage12-retrieval-trace-v1:{trace_id}")
    payload = {
        "workspace_id": str(projection.workspace_id),
        "base_id": str(projection.base_id),
        "table_id": str(projection.table_id),
        "record_id": (
            None if projection.record_id is None else str(projection.record_id)
        ),
        "source_type": projection.source_type,
        "source_id": projection.source_id,
        "source_version": projection.source_version,
        "content_hash": projection.content_hash,
        "visibility_profile_hash": projection.visibility_profile_hash,
        "scope_hash": projection.scope_hash,
        "trace_id": trace_ref,
    }
    idempotency_key = "stage12:retrieval:index:" + _sha256(
        ":".join(
            (
                str(projection.workspace_id),
                projection.source_type,
                projection.source_id,
                str(projection.source_version),
                projection.visibility_profile_hash,
                projection.content_hash,
            )
        )
    )
    expected = OutboxEvent(
        id=uuid4(),
        event_type=_REQUEST_EVENT,
        aggregate_type="stage12_retrieval_source",
        aggregate_id=projection.source_id,
        payload=payload,
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        trace_id=trace_ref,
        created_at=now,
    )
    existing = uow.get_outbox_event_by_idempotency_key(idempotency_key)
    if existing is not None:
        if not _projection_events_equal(existing, expected):
            raise ValueError("retrieval_projection_event_conflict")
        return existing
    uow.add_outbox_event(expected)
    return expected


def process_retrieval_projection_event(
    uow: RetrievalIndexUnitOfWork,
    event: OutboxEvent,
    *,
    projection_reader: ProjectionReader,
    token_counter: TokenCounter,
    provider: EmbeddingDocumentProvider,
    now: datetime,
) -> RetrievalIndexingResult:
    reference = _request_reference(event)
    if reference is None:
        return RetrievalIndexingResult(
            status="failed",
            error_code="retrieval_projection_event_invalid",
        )
    if event.status == "processed":
        matching = _matching_sources(uow, reference)
        active = next((source for source in matching if source.is_active), None)
        return RetrievalIndexingResult(
            status="indexed" if active is not None else "discarded",
            source_version=None if active is None else active.source_version,
            indexed_chunk_count=(
                0 if active is None else len(uow.list_chunks(active.id))
            ),
            error_code="none" if active is not None else "retrieval_projection_stale",
        )
    try:
        projection = projection_reader(dict(reference))
    except Exception:
        return RetrievalIndexingResult(
            status="failed",
            error_code="retrieval_projection_read_failed",
        )
    if projection is None or not _projection_matches_reference(
        projection,
        reference,
    ):
        _mark_event_processed(event, now)
        return RetrievalIndexingResult(
            status="discarded",
            error_code="retrieval_projection_stale",
        )
    profile_error = _profile_error(uow, provider.profile)
    if profile_error is not None:
        return RetrievalIndexingResult(status="failed", error_code=profile_error)
    try:
        chunks = chunk_projection(
            projection,
            token_counter=token_counter,
            max_tokens=provider.profile.max_input_tokens,
            overlap_tokens=min(32, provider.profile.max_input_tokens - 1),
        )
    except (TypeError, ValueError):
        return RetrievalIndexingResult(
            status="failed",
            error_code="retrieval_projection_invalid",
        )

    prior = next(
        (
            source
            for source in reversed(_matching_sources(uow, reference))
            if source.is_active
        ),
        None,
    )
    reused = prior is not None and prior.content_hash == projection.content_hash
    if reused:
        embeddings = _reusable_embeddings(uow, prior, chunks)
        if embeddings is None:
            reused = False
    if not reused:
        try:
            raw_embeddings = provider.embed_documents(
                tuple(chunk.chunk_text for chunk in chunks)
            )
            embeddings = validate_embedding_batch(
                raw_embeddings,
                expected_count=len(chunks),
                dimension=provider.profile.dimension,
            )
        except EmbeddingProviderError as error:
            return RetrievalIndexingResult(status="failed", error_code=error.code)
        except Exception:
            return RetrievalIndexingResult(
                status="failed",
                error_code="embedding_provider_unavailable",
            )
    assert embeddings is not None

    source = Stage12RetrievalSource(
        id=uuid4(),
        workspace_id=projection.workspace_id,
        base_id=projection.base_id,
        table_id=projection.table_id,
        record_id=projection.record_id,
        field_ids=list(projection.field_ids),
        source_type=projection.source_type,
        source_identity=projection.source_id,
        source_version=projection.source_version,
        embedding_profile=provider.profile.profile_name,
        visibility_profile_hash=projection.visibility_profile_hash,
        scope_hash=projection.scope_hash,
        content_hash=projection.content_hash,
        status="pending",
        is_active=False,
        activated_at=None,
        revoked_at=None,
        created_at=now,
        updated_at=now,
    )
    pending_chunks = tuple(
        Stage12RetrievalChunk(
            id=uuid4(),
            workspace_id=projection.workspace_id,
            source_id=source.id,
            source_version=projection.source_version,
            ordinal=chunk.ordinal,
            chunk_kind=chunk.chunk_kind,
            source_type=chunk.source_type,
            table_id=chunk.table_id,
            record_id=chunk.record_id,
            field_ids=list(chunk.field_ids),
            start_token=chunk.start_token,
            end_token=chunk.end_token,
            chunk_text=chunk.chunk_text,
            keyword_terms=list(chunk.keyword_terms),
            content_hash=chunk.content_hash,
            visibility_profile_hash=chunk.visibility_profile_hash,
            scope_hash=chunk.scope_hash,
            embedding_profile=provider.profile.profile_name,
            embedding=list(embedding),
            status="pending",
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    )
    try:
        with uow.atomic():
            uow.add_source(source)
            uow.flush()
            for pending_chunk in pending_chunks:
                uow.add_chunk(pending_chunk)
            uow.flush()
            activate_retrieval_source_version(
                uow,
                source,
                now=now,
            )
    except Exception:
        return RetrievalIndexingResult(
            status="failed",
            error_code="retrieval_index_write_failed",
        )
    _mark_event_processed(event, now)
    return RetrievalIndexingResult(
        status="indexed",
        source_version=source.source_version,
        indexed_chunk_count=len(pending_chunks),
        reused_embedding=reused,
    )


def activate_retrieval_source_version(
    uow: RetrievalIndexUnitOfWork,
    source: Stage12RetrievalSource,
    *,
    now: datetime,
) -> None:
    sources = uow.list_sources(
        workspace_id=source.workspace_id,
        source_type=source.source_type,
        source_identity=source.source_identity,
        visibility_profile_hash=source.visibility_profile_hash,
    )
    for previous in sources:
        if previous.id == source.id or not previous.is_active:
            continue
        previous.is_active = False
        previous.status = "stale"
        for chunk in uow.list_chunks(previous.id):
            if chunk.status == "indexed":
                chunk.status = "stale"
    uow.flush()
    source.status = "indexed"
    source.is_active = True
    source.activated_at = now
    for chunk in uow.list_chunks(source.id):
        chunk.status = "indexed"
    uow.flush()


def revoke_retrieval_source(
    uow: RetrievalIndexUnitOfWork,
    *,
    workspace_id: UUID,
    source_type: str,
    source_identity: str,
    visibility_profile_hash: str,
    reason_code: str,
    now: datetime,
) -> RetrievalRevocationResult:
    if _SAFE_REASON.fullmatch(reason_code) is None:
        raise ValueError("retrieval_revoke_reason_invalid")
    sources = uow.list_sources(
        workspace_id=workspace_id,
        source_type=source_type,
        source_identity=source_identity,
        visibility_profile_hash=visibility_profile_hash,
    )
    revoked_sources = 0
    revoked_chunks = 0
    with uow.atomic():
        for source in sources:
            if source.status == "revoked":
                continue
            revoked_sources += 1
            source.status = "revoked"
            source.is_active = False
            source.revoked_at = now
            for chunk in uow.list_chunks(source.id):
                if chunk.status != "revoked":
                    chunk.status = "revoked"
                    chunk.revoked_at = now
                    revoked_chunks += 1
        uow.flush()
    source_ids = tuple(sorted(str(source.id) for source in sources))
    trace_ref = _sha256(
        f"stage12-revoke:{workspace_id}:{source_type}:"
        f"{source_identity}:{visibility_profile_hash}:{reason_code}"
    )
    event = OutboxEvent(
        id=uuid4(),
        event_type=_REVOKE_EVENT,
        aggregate_type="stage12_retrieval_source",
        aggregate_id=source_identity,
        payload={
            "workspace_id": str(workspace_id),
            "source_type": source_type,
            "source_id": source_identity,
            "source_ids": source_ids,
            "visibility_profile_hash": visibility_profile_hash,
            "reason_code": reason_code,
            "trace_id": trace_ref,
        },
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key="stage12:retrieval:revoke:" + trace_ref,
        trace_id=trace_ref,
        created_at=now,
    )
    existing = uow.get_outbox_event_by_idempotency_key(event.idempotency_key)
    if existing is None:
        uow.add_outbox_event(event)
    else:
        event = existing
    return RetrievalRevocationResult(
        revoked_source_count=revoked_sources,
        revoked_chunk_count=revoked_chunks,
        event=event,
    )


def rollback_retrieval_profile(
    uow: RetrievalIndexUnitOfWork,
    *,
    selected_profile: str,
    fallback_profile: str,
    now: datetime,
) -> RetrievalProfileRollbackResult:
    selected = uow.get_profile(selected_profile)
    fallback = uow.get_profile(fallback_profile)
    if (
        selected is None
        or fallback is None
        or selected.status != "active"
        or fallback.status not in {"candidate", "retired"}
    ):
        return RetrievalProfileRollbackResult(
            status="failed",
            reactivated_source_count=0,
        )
    fallback_sources = uow.list_sources(embedding_profile=fallback_profile)
    latest: dict[tuple[UUID, str, str, str], Stage12RetrievalSource] = {}
    for source in fallback_sources:
        key = (
            source.workspace_id,
            source.source_type,
            source.source_identity,
            source.visibility_profile_hash,
        )
        if key not in latest or source.source_version > latest[key].source_version:
            latest[key] = source
    if not latest:
        return RetrievalProfileRollbackResult(
            status="failed",
            reactivated_source_count=0,
        )
    with uow.atomic():
        selected.status = "retired"
        selected.retired_at = now
        uow.flush()
        fallback.status = "active"
        fallback.activated_at = now
        fallback.retired_at = None
        uow.flush()
        for source in uow.list_sources(embedding_profile=selected_profile):
            if source.is_active:
                source.is_active = False
                source.status = "stale"
                for chunk in uow.list_chunks(source.id):
                    if chunk.status == "indexed":
                        chunk.status = "stale"
        uow.flush()
        for source in latest.values():
            source.status = "indexed"
            source.is_active = True
            source.activated_at = now
            source.revoked_at = None
            for chunk in uow.list_chunks(source.id):
                chunk.status = "indexed"
                chunk.revoked_at = None
        uow.flush()
    return RetrievalProfileRollbackResult(
        status="rolled_back",
        reactivated_source_count=len(latest),
    )


def _source_change_reference(event: OutboxEvent) -> dict[str, object] | None:
    payload = event.payload
    if (
        event.event_type != _SOURCE_CHANGE_EVENT
        or event.aggregate_type != "stage12_retrieval_source"
        or event.status not in {"pending", "processing", "processed"}
        or not isinstance(payload, dict)
        or set(payload) != _SOURCE_CHANGE_KEYS
        or payload.get("trace_id") != event.trace_id
        or not _hash(payload.get("trace_id"))
        or payload.get("source_type")
        not in {"schema_table", "schema_field", "record", "record_field"}
        or not isinstance(payload.get("source_id"), str)
        or not str(payload["source_id"]).strip()
        or payload["source_id"] != str(payload["source_id"]).strip()
        or len(str(payload["source_id"])) > 240
        or "\r" in str(payload["source_id"])
        or "\n" in str(payload["source_id"])
        or event.aggregate_id != payload["source_id"]
        or payload.get("mutation_kind") not in _SOURCE_CHANGE_KINDS
        or not isinstance(payload.get("source_version"), int)
        or isinstance(payload.get("source_version"), bool)
        or int(payload["source_version"]) < 1
    ):
        return None
    try:
        UUID(str(payload["workspace_id"]))
        UUID(str(payload["base_id"]))
        UUID(str(payload["table_id"]))
        if payload["record_id"] is not None:
            UUID(str(payload["record_id"]))
    except (TypeError, ValueError):
        return None
    record_source = payload["source_type"] in {"record", "record_field"}
    if record_source != (payload["record_id"] is not None):
        return None
    return dict(payload)


def _projection_matches_source_reference(
    projection: RetrievalProjectionV2,
    reference: dict[str, object],
) -> bool:
    return (
        str(projection.workspace_id) == reference["workspace_id"]
        and str(projection.base_id) == reference["base_id"]
        and str(projection.table_id) == reference["table_id"]
        and (None if projection.record_id is None else str(projection.record_id))
        == reference["record_id"]
        and projection.source_type == reference["source_type"]
        and _normalized_source_identity(projection.source_id)
        == _normalized_source_identity(str(reference["source_id"]))
        and projection.source_version == reference["source_version"]
    )


def _request_reference(event: OutboxEvent) -> dict[str, object] | None:
    payload = event.payload
    if (
        event.event_type != _REQUEST_EVENT
        or event.aggregate_type != "stage12_retrieval_source"
        or event.status not in {"pending", "processing", "processed"}
        or not isinstance(payload, dict)
        or set(payload) != _REQUEST_KEYS
        or payload.get("trace_id") != event.trace_id
        or not _hash(payload.get("trace_id"))
        or not _hash(payload.get("content_hash"))
        or not _hash(payload.get("visibility_profile_hash"))
        or not _hash(payload.get("scope_hash"))
        or payload.get("source_type")
        not in {"schema_table", "schema_field", "record", "record_field"}
        or not isinstance(payload.get("source_id"), str)
        or not str(payload["source_id"]).strip()
        or payload["source_id"] != str(payload["source_id"]).strip()
        or len(str(payload["source_id"])) > 240
        or "\r" in str(payload["source_id"])
        or "\n" in str(payload["source_id"])
        or event.aggregate_id != payload["source_id"]
        or not isinstance(payload.get("source_version"), int)
        or isinstance(payload.get("source_version"), bool)
        or payload["source_version"] < 1
    ):
        return None
    try:
        UUID(str(payload["workspace_id"]))
        UUID(str(payload["base_id"]))
        UUID(str(payload["table_id"]))
        if payload["record_id"] is not None:
            UUID(str(payload["record_id"]))
    except (TypeError, ValueError):
        return None
    return dict(payload)


def _projection_matches_reference(
    projection: RetrievalProjectionV2,
    reference: dict[str, object],
) -> bool:
    return (
        str(projection.workspace_id) == reference["workspace_id"]
        and str(projection.base_id) == reference["base_id"]
        and str(projection.table_id) == reference["table_id"]
        and (None if projection.record_id is None else str(projection.record_id))
        == reference["record_id"]
        and projection.source_type == reference["source_type"]
        and projection.source_id == reference["source_id"]
        and projection.source_version == reference["source_version"]
        and projection.content_hash == reference["content_hash"]
        and projection.visibility_profile_hash == reference["visibility_profile_hash"]
        and projection.scope_hash == reference["scope_hash"]
    )


def _profile_error(
    uow: RetrievalIndexUnitOfWork,
    profile: EmbeddingProfileV1,
) -> str | None:
    stored = uow.get_profile(_SELECTED_PROFILE)
    if (
        stored is None
        or stored.status != "active"
        or profile.profile_name != _SELECTED_PROFILE
        or profile.model_revision != _SELECTED_REVISION
        or profile.dimension != 1024
        or stored.model_revision != profile.model_revision
        or stored.dimension != profile.dimension
        or stored.normalization != profile.normalization
        or stored.distance_metric != profile.distance_metric
    ):
        return "embedding_profile_mismatch"
    return None


def _matching_sources(
    uow: RetrievalIndexUnitOfWork,
    reference: dict[str, object],
) -> list[Stage12RetrievalSource]:
    return uow.list_sources(
        workspace_id=UUID(str(reference["workspace_id"])),
        source_type=str(reference["source_type"]),
        source_identity=str(reference["source_id"]),
        visibility_profile_hash=str(reference["visibility_profile_hash"]),
    )


def _reusable_embeddings(
    uow: RetrievalIndexUnitOfWork,
    source: Stage12RetrievalSource,
    chunks: tuple[RetrievalChunkV2, ...],
) -> tuple[tuple[float, ...], ...] | None:
    stored = uow.list_chunks(source.id)
    if len(stored) != len(chunks):
        return None
    ordered = sorted(stored, key=lambda item: item.ordinal)
    if any(
        stored_chunk.ordinal != projected_chunk.ordinal
        or stored_chunk.content_hash != projected_chunk.content_hash
        or stored_chunk.embedding is None
        for stored_chunk, projected_chunk in zip(ordered, chunks, strict=True)
    ):
        return None
    try:
        return validate_embedding_batch(
            tuple(tuple(chunk.embedding or ()) for chunk in ordered),
            expected_count=len(ordered),
            dimension=1024,
        )
    except EmbeddingProviderError:
        return None


def _events_equal(left: OutboxEvent, right: OutboxEvent) -> bool:
    return (
        left.event_type == right.event_type
        and left.aggregate_type == right.aggregate_type
        and left.aggregate_id == right.aggregate_id
        and left.payload == right.payload
        and left.trace_id == right.trace_id
    )


def _projection_events_equal(left: OutboxEvent, right: OutboxEvent) -> bool:
    left_payload = dict(left.payload)
    right_payload = dict(right.payload)
    left_payload.pop("trace_id", None)
    right_payload.pop("trace_id", None)
    return (
        left.event_type == right.event_type == _REQUEST_EVENT
        and left.aggregate_type == right.aggregate_type
        and left.aggregate_id == right.aggregate_id
        and left.payload.get("trace_id") == left.trace_id
        and right.payload.get("trace_id") == right.trace_id
        and left_payload == right_payload
    )


def _mark_event_processed(event: OutboxEvent, now: datetime) -> None:
    event.status = "processed"
    event.processed_at = now
    event.last_error = None
    event.last_error_redacted = None


def _valid_trace(value: object) -> bool:
    return (
        isinstance(value, str)
        and value == value.strip()
        and bool(value)
        and len(value) <= 120
        and "\r" not in value
        and "\n" not in value
    )


def _valid_bootstrap_cursor(value: object) -> bool:
    return (
        isinstance(value, str)
        and value == value.strip()
        and bool(value)
        and len(value) <= 500
        and "\r" not in value
        and "\n" not in value
        and "|" in value
    )


def _hash(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _normalized_source_identity(value: str) -> str:
    return (
        value.replace("schema-table:", "schema_table:")
        .replace("schema-field:", "schema_field:")
        .replace("record-field:", "record_field:")
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
