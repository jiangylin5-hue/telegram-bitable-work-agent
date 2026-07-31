from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import app.services.retrieval_v2_runtime as retrieval_runtime
import app.workers.retrieval_v2_outbox as retrieval_outbox_worker
from app.models.stage12_retrieval import (
    Stage12RelationEdge,
    Stage12RetrievalChunk,
    Stage12RetrievalProfile,
    Stage12RetrievalSource,
)
from app.schemas.retrieval_v2 import EmbeddingProfileV1
from app.services.agent_field_policy_v2 import build_stage12_field_policy_v2
from app.services.agent_schema_binding import build_authorized_schema_snapshot
from app.services.authorized_query_records import build_authorized_query_context
from app.services.permissions import Actor
from app.services.retrieval_v2_indexing import (
    request_retrieval_projection,
    request_retrieval_source_change,
)
from app.services.stage06_digital_employees import create_digital_employee
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    update_record,
)


NOW = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)


class _Counter:
    def encode(self, text: str) -> tuple[int, ...]:
        return tuple(ord(item) for item in text)

    def decode(self, token_ids: tuple[int, ...]) -> str:
        return "".join(chr(item) for item in token_ids)


class _Provider:
    profile = EmbeddingProfileV1(
        version="embedding-profile.v1",
        profile_name="stage12.openrouter-bge-m3-v1",
        model_revision="baai/bge-m3-20251117",
        dimension=1024,
        normalization="l2",
        distance_metric="cosine",
        max_input_tokens=8192,
        batch_size=64,
        provider_location="remote",
        data_residency="synthetic-test-only",
    )

    def embed_documents(self, texts: tuple[str, ...]):
        return tuple((1.0,) + (0.0,) * 1023 for _ in texts)


def _authorized_fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="registration-owner", role="owner")
    workspace = create_workspace(
        uow,
        name="Retrieval registration",
        owner_user_id=actor.actor_id,
        actor=actor,
    )
    base = create_base(uow, workspace.id, name="Registration Base", actor=actor)
    table = create_table(
        uow,
        base.id,
        name="Work items",
        key="registration_work_items",
        actor=actor,
    )
    field = create_field(
        uow,
        table.id,
        name="Title",
        key="title",
        field_type="text",
        actor=actor,
    )
    record = create_record(
        uow,
        table.id,
        values={"title": "Atlas registered projection"},
        actor=actor,
    )
    employee = create_digital_employee(
        uow,
        base.id,
        name="Registration employee",
        description="Stage12 registration",
        telegram_alias=None,
        accessible_tables=[str(table.id)],
        accessible_views=[],
        field_policy=build_stage12_field_policy_v2(
            readable_field_ids=(field.id,),
            writable_field_ids=(),
        ),
        allowed_actions=["query"],
        actor=actor,
    )
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=workspace.id,
        employee_id=employee.id,
        actor=actor,
        require_field_policy_v2=True,
    )
    context = build_authorized_query_context(
        uow,
        workspace_id=workspace.id,
        base_id=base.id,
        employee_id=employee.id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    return uow, context, employee, table, field, record


def test_current_authority_creates_and_refreshes_bounded_safe_registration() -> None:
    uow, context, employee, *_ = _authorized_fixture()
    register = getattr(
        retrieval_runtime,
        "register_authorized_retrieval_scope",
        lambda *args, **kwargs: None,
    )

    created = register(uow.stage12_retrieval_uow, context=context, now=NOW)

    assert created is not None
    assert created.workspace_id == context.workspace_id
    assert created.base_id == context.base_id
    assert created.employee_id == employee.id
    assert created.actor_type == "user"
    assert created.actor_id == context.actor.actor_id
    assert created.scope_view_ids == []
    assert created.allow_whole_table is True
    assert created.status == "active"
    assert created.last_seen_at == NOW
    assert created.expires_at == NOW + timedelta(minutes=15)
    assert created.revoked_at is None
    assert len(uow.stage12_retrieval_uow.registrations) == 1
    assert not {
        "canonical_text",
        "record_values",
        "provider_payload",
        "credentials",
    } & set(created.__table__.c.keys())

    refreshed = register(
        uow.stage12_retrieval_uow,
        context=context,
        now=NOW + timedelta(minutes=1),
    )

    assert refreshed.id == created.id
    assert len(uow.stage12_retrieval_uow.registrations) == 1
    assert refreshed.last_seen_at == NOW + timedelta(minutes=1)
    assert refreshed.expires_at == NOW + timedelta(minutes=16)


def test_new_registration_enqueues_one_reference_only_bootstrap_not_refresh() -> None:
    uow, context, *_ = _authorized_fixture()
    index = uow.stage12_retrieval_uow

    registration = retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW,
    )

    bootstrap = [
        event
        for event in index.outbox_events
        if event.event_type == "stage12.retrieval_scope.bootstrap_requested"
    ]
    assert len(bootstrap) == 1
    event = bootstrap[0]
    assert event.aggregate_type == "stage12_retrieval_scope_registration"
    assert event.aggregate_id == str(registration.id)
    assert set(event.payload) == {
        "workspace_id",
        "registration_id",
        "cursor",
        "page_size",
        "trace_id",
    }
    assert event.payload == {
        "workspace_id": str(context.workspace_id),
        "registration_id": str(registration.id),
        "cursor": None,
        "page_size": 200,
        "trace_id": event.trace_id,
    }
    assert not {
        "canonical_text",
        "record_values",
        "provider_payload",
        "credentials",
    } & set(event.payload)

    retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW + timedelta(minutes=1),
    )

    assert (
        len(
            [
                item
                for item in index.outbox_events
                if item.event_type == "stage12.retrieval_scope.bootstrap_requested"
            ]
        )
        == 1
    )


def test_bootstrap_pages_stable_existing_sources_and_continues_bounded() -> None:
    uow, context, *_ = _authorized_fixture()
    index = uow.stage12_retrieval_uow
    registration = retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW,
    )
    request_bootstrap = getattr(
        retrieval_runtime,
        "request_retrieval_scope_bootstrap",
        None,
    )
    assert request_bootstrap is not None
    index.outbox_events.clear()
    first = request_bootstrap(
        index,
        workspace_id=context.workspace_id,
        registration_id=registration.id,
        cursor=None,
        page_size=2,
        trace_id="bootstrap-existing-sources",
        now=NOW,
    )
    first.status = "processing"
    handlers = retrieval_outbox_worker.build_registered_retrieval_v2_outbox_handlers(
        platform_uow=uow,
        uow=index,
        token_counter=object(),
        embedding_provider=object(),
        now=lambda: NOW + timedelta(minutes=1),
    )

    bootstrap_handler = handlers.get("stage12.retrieval_scope.bootstrap_requested")
    assert bootstrap_handler is not None
    bootstrap_handler(first)

    requested = [
        item
        for item in index.outbox_events
        if item.event_type == "stage12.retrieval_projection.requested"
    ]
    continuations = [
        item
        for item in index.outbox_events
        if item.event_type == "stage12.retrieval_scope.bootstrap_requested"
        and item.id != first.id
    ]
    assert len(requested) == 2
    assert len(continuations) == 1
    assert continuations[0].payload["cursor"]
    assert continuations[0].payload["page_size"] == 2

    continuations[0].status = "processing"
    bootstrap_handler(continuations[0])

    requested = [
        item
        for item in index.outbox_events
        if item.event_type == "stage12.retrieval_projection.requested"
    ]
    assert {item.payload["source_type"] for item in requested} == {
        "schema_table",
        "schema_field",
        "record",
    }
    assert not [
        item
        for item in index.outbox_events
        if item.event_type == "stage12.retrieval_scope.bootstrap_requested"
        and item.id not in {first.id, continuations[0].id}
    ]


def test_stale_bootstrap_cannot_enqueue_after_registration_revocation() -> None:
    uow, context, employee, *_ = _authorized_fixture()
    index = uow.stage12_retrieval_uow
    registration = retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW,
    )
    bootstrap = next(
        event
        for event in index.outbox_events
        if event.event_type == "stage12.retrieval_scope.bootstrap_requested"
    )
    employee.field_policy = {}
    employee.version += 1
    bootstrap.status = "processing"
    handlers = retrieval_outbox_worker.build_registered_retrieval_v2_outbox_handlers(
        platform_uow=uow,
        uow=index,
        token_counter=object(),
        embedding_provider=object(),
        now=lambda: NOW + timedelta(minutes=1),
    )

    handler = handlers.get("stage12.retrieval_scope.bootstrap_requested")
    assert handler is not None
    handler(bootstrap)

    assert registration.status == "revoked"
    assert not [
        item
        for item in index.outbox_events
        if item.event_type == "stage12.retrieval_projection.requested"
    ]


def test_bootstrap_continuation_revalidates_authority_before_next_page() -> None:
    uow, context, employee, *_ = _authorized_fixture()
    index = uow.stage12_retrieval_uow
    registration = retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW,
    )
    index.outbox_events.clear()
    first = retrieval_runtime.request_retrieval_scope_bootstrap(
        index,
        workspace_id=context.workspace_id,
        registration_id=registration.id,
        cursor=None,
        page_size=1,
        trace_id="bootstrap-continuation-revalidation",
        now=NOW,
    )
    handlers = retrieval_outbox_worker.build_registered_retrieval_v2_outbox_handlers(
        platform_uow=uow,
        uow=index,
        token_counter=object(),
        embedding_provider=object(),
        now=lambda: NOW + timedelta(minutes=1),
    )
    handler = handlers["stage12.retrieval_scope.bootstrap_requested"]
    first.status = "processing"
    handler(first)
    continuation = next(
        item
        for item in index.outbox_events
        if item.event_type == "stage12.retrieval_scope.bootstrap_requested"
        and item.id != first.id
    )
    initial_request_count = len(
        [
            item
            for item in index.outbox_events
            if item.event_type == "stage12.retrieval_projection.requested"
        ]
    )
    assert initial_request_count == 1

    employee.field_policy = {}
    employee.version += 1
    continuation.status = "processing"
    handler(continuation)

    assert registration.status == "revoked"
    assert (
        len(
            [
                item
                for item in index.outbox_events
                if item.event_type == "stage12.retrieval_projection.requested"
            ]
        )
        == initial_request_count
    )
    assert not [
        item
        for item in index.outbox_events
        if item.event_type == "stage12.retrieval_scope.bootstrap_requested"
        and item.id not in {first.id, continuation.id}
    ]


def test_reference_only_change_rebuilds_only_active_registered_projection() -> None:
    uow, context, _employee, table, _field, record = _authorized_fixture()
    retrieval_runtime.register_authorized_retrieval_scope(
        uow.stage12_retrieval_uow,
        context=context,
        now=NOW,
    )
    rebuild = getattr(
        retrieval_runtime,
        "build_registered_source_projections",
        lambda *args, **kwargs: (),
    )
    reference = {
        "workspace_id": str(context.workspace_id),
        "base_id": str(context.base_id),
        "table_id": str(table.id),
        "record_id": str(record.id),
        "source_type": "record",
        "source_id": f"record:{record.id}",
        "source_version": record.version,
        "mutation_kind": "record_changed",
        "trace_id": "a" * 64,
    }

    projections = rebuild(
        uow,
        uow.stage12_retrieval_uow,
        reference=reference,
        now=NOW + timedelta(minutes=2),
    )

    assert len(projections) == 1
    projection = projections[0]
    assert projection.source_id == f"record:{record.id}"
    assert projection.source_version == record.version
    assert projection.scope_hash == (
        uow.stage12_retrieval_uow.registrations[0].retrieval_scope_hash
    )
    assert "Atlas registered projection" in projection.canonical_text


def test_authority_contraction_revokes_registration_and_all_index_rows() -> None:
    uow, context, employee, table, field, record = _authorized_fixture()
    index = uow.stage12_retrieval_uow
    registration = retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW,
    )
    reference = {
        "workspace_id": str(context.workspace_id),
        "base_id": str(context.base_id),
        "table_id": str(table.id),
        "record_id": str(record.id),
        "source_type": "record",
        "source_id": f"record:{record.id}",
        "source_version": record.version,
        "mutation_kind": "permission_changed",
        "trace_id": "b" * 64,
    }
    projection = retrieval_runtime.build_registered_source_projections(
        uow,
        index,
        reference=reference,
        now=NOW + timedelta(minutes=1),
    )[0]
    source = Stage12RetrievalSource(
        id=uuid4(),
        workspace_id=context.workspace_id,
        base_id=context.base_id,
        table_id=table.id,
        record_id=record.id,
        field_ids=list(projection.field_ids),
        source_type="record",
        source_identity=projection.source_id,
        source_version=projection.source_version,
        embedding_profile="stage12.openrouter-bge-m3-v1",
        visibility_profile_hash=projection.visibility_profile_hash,
        scope_hash=projection.scope_hash,
        content_hash=projection.content_hash,
        status="indexed",
        is_active=True,
        activated_at=NOW,
        revoked_at=None,
    )
    chunk = Stage12RetrievalChunk(
        id=uuid4(),
        workspace_id=context.workspace_id,
        source_id=source.id,
        source_version=source.source_version,
        ordinal=0,
        chunk_kind="canonical",
        source_type="record",
        table_id=table.id,
        record_id=record.id,
        field_ids=list(projection.field_ids),
        start_token=0,
        end_token=1,
        chunk_text="Atlas",
        keyword_terms=["atlas"],
        content_hash=sha256(b"Atlas").hexdigest(),
        visibility_profile_hash=projection.visibility_profile_hash,
        scope_hash=projection.scope_hash,
        embedding_profile="stage12.openrouter-bge-m3-v1",
        embedding=[1.0] + [0.0] * 1023,
        status="indexed",
        revoked_at=None,
    )
    target = create_record(
        uow,
        table.id,
        values={"title": "Second record"},
        actor=context.actor,
    )
    edge = Stage12RelationEdge(
        id=uuid4(),
        workspace_id=context.workspace_id,
        relation_id=f"relation:{field.id}",
        source_table_id=table.id,
        source_record_id=record.id,
        link_field_id=field.id,
        target_table_id=table.id,
        target_record_id=target.id,
        direction="forward",
        source_version=record.version,
        target_version=target.version,
        visibility_profile_hash=projection.visibility_profile_hash,
        scope_hash=projection.scope_hash,
        edge_hash="c" * 64,
        status="active",
        revoked_at=None,
    )
    index.sources.append(source)
    index.chunks.append(chunk)
    index.relation_edges.append(edge)

    employee.field_policy = {}
    employee.version += 1
    revoked_at = NOW + timedelta(minutes=2)
    projections = retrieval_runtime.build_registered_source_projections(
        uow,
        index,
        reference=reference,
        now=revoked_at,
    )

    assert projections == ()
    assert registration.status == "revoked"
    assert registration.revoked_at == revoked_at
    assert source.status == "revoked"
    assert source.is_active is False
    assert source.revoked_at == revoked_at
    assert chunk.status == "revoked"
    assert chunk.revoked_at == revoked_at
    assert edge.status == "revoked"
    assert edge.revoked_at == revoked_at


def test_production_outbox_factory_uses_durable_registration_coordinator() -> None:
    uow, context, _employee, table, _field, record = _authorized_fixture()
    index = uow.stage12_retrieval_uow
    registration = retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW,
    )
    event = request_retrieval_source_change(
        index,
        workspace_id=context.workspace_id,
        base_id=context.base_id,
        table_id=table.id,
        record_id=record.id,
        source_type="record",
        source_identity=f"record:{record.id}",
        source_version=record.version,
        mutation_kind="record_changed",
        trace_id="registered-worker",
        now=NOW,
    )
    event.status = "processing"
    factory = getattr(
        retrieval_outbox_worker,
        "build_registered_retrieval_v2_outbox_handlers",
        lambda *args, **kwargs: {},
    )
    handlers = factory(
        platform_uow=uow,
        uow=index,
        token_counter=object(),
        embedding_provider=object(),
        now=lambda: NOW + timedelta(minutes=1),
    )

    handler = handlers.get("stage12.retrieval_source.changed")
    assert handler is not None
    handler(event)

    requested = [
        item
        for item in index.outbox_events
        if item.event_type == "stage12.retrieval_projection.requested"
    ]
    assert len(requested) == 1
    assert requested[0].payload["scope_hash"] == registration.retrieval_scope_hash


def test_registered_change_materializes_and_revokes_relation_index() -> None:
    uow, _context, employee, table, title, source = _authorized_fixture()
    actor = Actor(actor_type="user", actor_id="registration-owner", role="owner")
    link = create_field(
        uow,
        table.id,
        name="Related work",
        key="related_work",
        field_type="linked_record",
        options={"target_table_id": str(table.id)},
        actor=actor,
    )
    target = create_record(
        uow,
        table.id,
        values={"title": "Relation target"},
        actor=actor,
    )
    update_record(
        uow,
        source.id,
        values={
            "title": "Atlas registered projection",
            "related_work": [str(target.id)],
        },
        expected_version=source.version,
        actor=actor,
    )
    employee.field_policy = build_stage12_field_policy_v2(
        readable_field_ids=(title.id, link.id),
        writable_field_ids=(),
    )
    employee.version += 1
    snapshot = build_authorized_schema_snapshot(
        uow,
        workspace_id=employee.workspace_id,
        employee_id=employee.id,
        actor=actor,
        require_field_policy_v2=True,
    )
    context = build_authorized_query_context(
        uow,
        workspace_id=employee.workspace_id,
        base_id=employee.base_id,
        employee_id=employee.id,
        actor=actor,
        snapshot=snapshot,
        chat_authorized_view_ids=None,
        allow_whole_table=True,
    )
    index = uow.stage12_retrieval_uow
    retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW,
    )
    reference = {
        "workspace_id": str(context.workspace_id),
        "base_id": str(context.base_id),
        "table_id": str(table.id),
        "record_id": str(source.id),
        "source_type": "record",
        "source_id": f"record:{source.id}",
        "source_version": source.version,
        "mutation_kind": "link_changed",
        "trace_id": "d" * 64,
    }

    retrieval_runtime.build_registered_source_projections(
        uow,
        index,
        reference=reference,
        now=NOW + timedelta(minutes=1),
    )

    active = [edge for edge in index.relation_edges if edge.status == "active"]
    assert len(active) == 1
    assert active[0].source_record_id == source.id
    assert active[0].target_record_id == target.id
    assert active[0].link_field_id == link.id

    update_record(
        uow,
        source.id,
        values={"title": "Atlas registered projection", "related_work": []},
        expected_version=source.version,
        actor=actor,
    )
    reference["source_version"] = source.version
    revoked_at = NOW + timedelta(minutes=2)
    retrieval_runtime.build_registered_source_projections(
        uow,
        index,
        reference=reference,
        now=revoked_at,
    )

    assert not [edge for edge in index.relation_edges if edge.status == "active"]
    assert active[0].status == "revoked"
    assert active[0].revoked_at == revoked_at


def test_queued_projection_cannot_reactivate_a_revoked_registration_scope() -> None:
    uow, context, employee, table, _field, record = _authorized_fixture()
    index = uow.stage12_retrieval_uow
    registration = retrieval_runtime.register_authorized_retrieval_scope(
        index,
        context=context,
        now=NOW,
    )
    source_reference = {
        "workspace_id": str(context.workspace_id),
        "base_id": str(context.base_id),
        "table_id": str(table.id),
        "record_id": str(record.id),
        "source_type": "record",
        "source_id": f"record:{record.id}",
        "source_version": record.version,
        "mutation_kind": "permission_changed",
        "trace_id": "e" * 64,
    }
    projection = retrieval_runtime.build_registered_source_projections(
        uow,
        index,
        reference=source_reference,
        now=NOW + timedelta(minutes=1),
    )[0]
    queued = request_retrieval_projection(
        index,
        projection,
        trace_id="queued-before-contraction",
        now=NOW + timedelta(minutes=1),
    )
    index.profiles.append(
        Stage12RetrievalProfile(
            id=uuid4(),
            profile_name=_Provider.profile.profile_name,
            model_revision=_Provider.profile.model_revision,
            dimension=1024,
            normalization="l2",
            distance_metric="cosine",
            max_input_tokens=8192,
            batch_size=64,
            provider_location="remote",
            data_residency="synthetic-test-only",
            profile_hash="f" * 64,
            status="active",
            activated_at=NOW,
            retired_at=None,
        )
    )

    employee.field_policy = {}
    employee.version += 1
    retrieval_runtime.build_registered_source_projections(
        uow,
        index,
        reference=source_reference,
        now=NOW + timedelta(minutes=2),
    )
    assert registration.status == "revoked"

    handlers = retrieval_outbox_worker.build_registered_retrieval_v2_outbox_handlers(
        platform_uow=uow,
        uow=index,
        token_counter=_Counter(),
        embedding_provider=_Provider(),
        now=lambda: NOW + timedelta(minutes=3),
    )
    queued.status = "processing"
    handlers["stage12.retrieval_projection.requested"](queued)

    assert queued.status == "processed"
    assert not [source for source in index.sources if source.is_active]
