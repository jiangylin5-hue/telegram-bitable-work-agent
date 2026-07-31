from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.models.stage12_retrieval import Stage12RetrievalProfile
from app.repositories.outbox import InMemoryOutboxRepository
from app.schemas.retrieval_v2 import EmbeddingProfileV1, RetrievalProjectionV2
from app.services.retrieval_v2_embeddings import EmbeddingProviderError
from app.services.retrieval_v2_indexing import (
    MemoryRetrievalIndexUnitOfWork,
    request_retrieval_projection,
    request_retrieval_source_change,
    revoke_retrieval_source,
)
from app.workers.outbox_dispatcher import OutboxDispatcher
from app.workers.retrieval_v2_outbox import build_retrieval_v2_outbox_handlers


NOW = datetime(2026, 7, 30, 15, 0, tzinfo=UTC)
PROFILE = "stage12.openrouter-bge-m3-v1"


class Counter:
    def encode(self, text):
        return tuple(ord(item) for item in text)

    def decode(self, token_ids):
        return "".join(chr(item) for item in token_ids)


class Provider:
    profile = EmbeddingProfileV1(
        version="embedding-profile.v1",
        profile_name=PROFILE,
        model_revision="baai/bge-m3-20251117",
        dimension=1024,
        normalization="l2",
        distance_metric="cosine",
        max_input_tokens=8192,
        batch_size=64,
        provider_location="remote",
        data_residency="synthetic-test-only",
    )

    def embed_documents(self, texts):
        return tuple((1.0,) + (0.0,) * 1023 for _ in texts)


class FailingProvider(Provider):
    def embed_documents(self, texts):
        raise EmbeddingProviderError("embedding_provider_unavailable")


class RateLimitedProvider(Provider):
    def embed_documents(self, texts):
        raise EmbeddingProviderError("embedding_provider_rate_limited")


class FailingWriteUnitOfWork(MemoryRetrievalIndexUnitOfWork):
    def add_source(self, source):
        raise RuntimeError("sensitive database detail")


class FailingProjectionEnqueueUnitOfWork(MemoryRetrievalIndexUnitOfWork):
    fail_projection_enqueue = False

    def add_outbox_event(self, event):
        if (
            self.fail_projection_enqueue
            and event.event_type == "stage12.retrieval_projection.requested"
        ):
            raise RuntimeError("sensitive enqueue detail")
        super().add_outbox_event(event)


def _projection() -> RetrievalProjectionV2:
    text = "[table] 工作项\n[record] CASE-42\n[标题] Atlas 回滚检查"
    return RetrievalProjectionV2(
        version="retrieval-projection.v2",
        source_type="record",
        source_id="record:case-42",
        source_version=3,
        workspace_id=uuid4(),
        base_id=uuid4(),
        table_id=uuid4(),
        record_id=uuid4(),
        field_ids=(uuid4(),),
        visibility_profile_hash="b" * 64,
        scope_hash="c" * 64,
        content_hash=sha256(text.encode()).hexdigest(),
        canonical_text=text,
    )


def _schema_projection() -> RetrievalProjectionV2:
    workspace_id = uuid4()
    base_id = uuid4()
    table_id = uuid4()
    field_id = uuid4()
    text = "[table] Work items\n[field] Title"
    return RetrievalProjectionV2(
        version="retrieval-projection.v2",
        source_type="schema_table",
        source_id=f"schema-table:{table_id}",
        source_version=2,
        workspace_id=workspace_id,
        base_id=base_id,
        table_id=table_id,
        record_id=None,
        field_ids=(field_id,),
        visibility_profile_hash="b" * 64,
        scope_hash="c" * 64,
        content_hash=sha256(text.encode()).hexdigest(),
        canonical_text=text,
    )


def test_outbox_callbacks_expand_reference_then_materialize_registered_projection() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection()
    uow.profiles.append(
        Stage12RetrievalProfile(
            id=uuid4(),
            profile_name=PROFILE,
            model_revision="baai/bge-m3-20251117",
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
            profile_hash="a" * 64,
            status="active",
            activated_at=NOW,
            retired_at=None,
        )
    )
    source_event = request_retrieval_source_change(
        uow,
        workspace_id=projection.workspace_id,
        base_id=projection.base_id,
        table_id=projection.table_id,
        record_id=projection.record_id,
        source_type=projection.source_type,
        source_identity=projection.source_id,
        source_version=projection.source_version,
        mutation_kind="record_changed",
        trace_id="runtime-worker-source-change",
        now=NOW,
    )
    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    first = OutboxDispatcher(
        repository=InMemoryOutboxRepository([source_event]),
        handlers=handlers,
    ).dispatch_once()
    requested = next(
        item
        for item in uow.outbox_events
        if item.event_type == "stage12.retrieval_projection.requested"
    )
    second = OutboxDispatcher(
        repository=InMemoryOutboxRepository([requested]),
        handlers=handlers,
    ).dispatch_once()

    assert first.processed == 1
    assert second.processed == 1
    assert source_event.status == "processed"
    assert requested.status == "processed"
    assert len(uow.sources) == 1
    assert uow.sources[0].is_active is True
    assert all(item.status == "indexed" for item in uow.chunks)


def test_schema_source_change_accepts_canonical_projection_identity() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _schema_projection()
    source_event = request_retrieval_source_change(
        uow,
        workspace_id=projection.workspace_id,
        base_id=projection.base_id,
        table_id=projection.table_id,
        record_id=None,
        source_type="schema_table",
        source_identity=f"schema_table:{projection.table_id}",
        source_version=projection.source_version,
        mutation_kind="schema_changed",
        trace_id="runtime-worker-schema-source-change",
        now=NOW,
    )
    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([source_event]),
        handlers=handlers,
    ).dispatch_once()

    requested = tuple(
        item
        for item in uow.outbox_events
        if item.event_type == "stage12.retrieval_projection.requested"
    )
    assert result.processed == 1
    assert result.dead_lettered == 0
    assert len(requested) == 1
    assert requested[0].aggregate_id == f"schema-table:{projection.table_id}"


def test_schema_rebuild_recognizes_already_materialized_canonical_identity() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _schema_projection()
    uow.profiles.append(
        Stage12RetrievalProfile(
            id=uuid4(),
            profile_name=PROFILE,
            model_revision="baai/bge-m3-20251117",
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
            profile_hash="a" * 64,
            status="active",
            activated_at=NOW,
            retired_at=None,
        )
    )
    projection_event = request_retrieval_projection(
        uow,
        projection,
        trace_id="runtime-worker-schema-initial-index",
        now=NOW,
    )
    initial_handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )
    indexed = OutboxDispatcher(
        repository=InMemoryOutboxRepository([projection_event]),
        handlers=initial_handlers,
    ).dispatch_once()
    source_event = request_retrieval_source_change(
        uow,
        workspace_id=projection.workspace_id,
        base_id=projection.base_id,
        table_id=projection.table_id,
        record_id=None,
        source_type="schema_table",
        source_identity=f"schema_table:{projection.table_id}",
        source_version=projection.source_version,
        mutation_kind="schema_changed",
        trace_id="runtime-worker-schema-existing-scope",
        now=NOW,
    )
    rebuild_handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    rebuilt = OutboxDispatcher(
        repository=InMemoryOutboxRepository([source_event]),
        handlers=rebuild_handlers,
    ).dispatch_once()

    assert indexed.processed == 1
    assert len(uow.sources) == 1
    assert uow.sources[0].source_identity == f"schema-table:{projection.table_id}"
    assert rebuilt.processed == 1
    assert rebuilt.dead_lettered == 0
    assert source_event.status == "processed"


def test_projection_provider_failure_is_retried_without_persisting_source() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection()
    uow.profiles.append(
        Stage12RetrievalProfile(
            id=uuid4(),
            profile_name=PROFILE,
            model_revision="baai/bge-m3-20251117",
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
            profile_hash="a" * 64,
            status="active",
            activated_at=NOW,
            retired_at=None,
        )
    )
    event = request_retrieval_projection(
        uow,
        projection,
        trace_id="runtime-worker-provider-failure",
        now=NOW,
    )
    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=FailingProvider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([event]),
        handlers=handlers,
    ).dispatch_once()

    assert result.retried == 1
    assert result.dead_lettered == 0
    assert event.status == "retry"
    assert event.attempts == 1
    assert event.last_error_redacted == "embedding_provider_unavailable"
    assert uow.sources == []


def test_projection_rate_limit_is_retried_instead_of_dead_lettered() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection()
    uow.profiles.append(
        Stage12RetrievalProfile(
            id=uuid4(),
            profile_name=PROFILE,
            model_revision="baai/bge-m3-20251117",
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
            profile_hash="a" * 64,
            status="active",
            activated_at=NOW,
            retired_at=None,
        )
    )
    event = request_retrieval_projection(
        uow,
        projection,
        trace_id="runtime-worker-rate-limit",
        now=NOW,
    )
    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=RateLimitedProvider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([event]),
        handlers=handlers,
    ).dispatch_once()

    assert result.retried == 1
    assert result.dead_lettered == 0
    assert event.status == "retry"
    assert event.last_error_redacted == "embedding_provider_rate_limited"


def test_projection_read_failure_is_retried_without_embedding() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection()
    event = request_retrieval_projection(
        uow,
        projection,
        trace_id="runtime-worker-read-failure",
        now=NOW,
    )

    def fail_read(reference):
        raise RuntimeError("sensitive reader detail")

    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=fail_read,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([event]),
        handlers=handlers,
    ).dispatch_once()

    assert result.retried == 1
    assert result.dead_lettered == 0
    assert event.status == "retry"
    assert event.last_error_redacted == "retrieval_projection_read_failed"
    assert "sensitive" not in event.last_error_redacted
    assert uow.sources == []


def test_source_projection_read_failure_is_retried_without_fanout() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection()
    event = request_retrieval_source_change(
        uow,
        workspace_id=projection.workspace_id,
        base_id=projection.base_id,
        table_id=projection.table_id,
        record_id=projection.record_id,
        source_type=projection.source_type,
        source_identity=projection.source_id,
        source_version=projection.source_version,
        mutation_kind="record_changed",
        trace_id="runtime-worker-source-read-failure",
        now=NOW,
    )

    def fail_read(reference):
        raise RuntimeError("sensitive source reader detail")

    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=fail_read,
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([event]),
        handlers=handlers,
    ).dispatch_once()

    assert result.retried == 1
    assert event.status == "retry"
    assert event.last_error_redacted == "retrieval_source_projection_read_failed"
    assert "sensitive" not in event.last_error_redacted
    assert not any(
        item.event_type == "stage12.retrieval_projection.requested"
        for item in uow.outbox_events
    )


def test_index_write_failure_is_retried_and_keeps_event_redacted() -> None:
    uow = FailingWriteUnitOfWork()
    projection = _projection()
    uow.profiles.append(
        Stage12RetrievalProfile(
            id=uuid4(),
            profile_name=PROFILE,
            model_revision="baai/bge-m3-20251117",
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
            profile_hash="a" * 64,
            status="active",
            activated_at=NOW,
            retired_at=None,
        )
    )
    event = request_retrieval_projection(
        uow,
        projection,
        trace_id="runtime-worker-write-failure",
        now=NOW,
    )
    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([event]),
        handlers=handlers,
    ).dispatch_once()

    assert result.retried == 1
    assert event.status == "retry"
    assert event.last_error_redacted == "retrieval_index_write_failed"
    assert "sensitive" not in event.last_error_redacted
    assert uow.sources == []


def test_projection_enqueue_failure_retries_source_change_atomically() -> None:
    uow = FailingProjectionEnqueueUnitOfWork()
    projection = _projection()
    event = request_retrieval_source_change(
        uow,
        workspace_id=projection.workspace_id,
        base_id=projection.base_id,
        table_id=projection.table_id,
        record_id=projection.record_id,
        source_type=projection.source_type,
        source_identity=projection.source_id,
        source_version=projection.source_version,
        mutation_kind="record_changed",
        trace_id="runtime-worker-enqueue-failure",
        now=NOW,
    )
    uow.fail_projection_enqueue = True
    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (projection,),
        registered_scope_profiles=frozenset(
            {(projection.visibility_profile_hash, projection.scope_hash)}
        ),
        projection_reader=lambda reference: projection,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([event]),
        handlers=handlers,
    ).dispatch_once()

    assert result.retried == 1
    assert event.status == "retry"
    assert event.last_error_redacted == "retrieval_source_projection_enqueue_failed"
    assert "sensitive" not in event.last_error_redacted
    assert not any(
        item.event_type == "stage12.retrieval_projection.requested"
        for item in uow.outbox_events
    )


def test_revocation_cleanup_event_is_consumed_without_reactivation() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection()
    revocation = revoke_retrieval_source(
        uow,
        workspace_id=projection.workspace_id,
        source_type=projection.source_type,
        source_identity=projection.source_id,
        visibility_profile_hash=projection.visibility_profile_hash,
        reason_code="permission_contracted",
        now=NOW,
    )
    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (),
        registered_scope_profiles=frozenset(),
        projection_reader=lambda reference: None,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([revocation.event]),
        handlers=handlers,
    ).dispatch_once()

    assert result.processed == 1
    assert result.missing_handler == 0
    assert result.dead_lettered == 0
    assert revocation.event.status == "processed"
    assert uow.sources == []
    assert uow.chunks == []


def test_forged_revocation_reference_is_dead_lettered() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection()
    revocation = revoke_retrieval_source(
        uow,
        workspace_id=projection.workspace_id,
        source_type=projection.source_type,
        source_identity=projection.source_id,
        visibility_profile_hash=projection.visibility_profile_hash,
        reason_code="permission_contracted",
        now=NOW,
    )
    revocation.event.payload["source_id"] = "record:forged"
    handlers = build_retrieval_v2_outbox_handlers(
        uow=uow,
        source_projection_reader=lambda reference: (),
        registered_scope_profiles=frozenset(),
        projection_reader=lambda reference: None,
        token_counter=Counter(),
        embedding_provider=Provider(),
        now=lambda: NOW,
    )

    result = OutboxDispatcher(
        repository=InMemoryOutboxRepository([revocation.event]),
        handlers=handlers,
    ).dispatch_once()

    assert result.processed == 0
    assert result.dead_lettered == 1
    assert result.missing_handler == 0
    assert revocation.event.status == "dead_letter"
    assert revocation.event.last_error_redacted == "retrieval_revocation_event_invalid"
