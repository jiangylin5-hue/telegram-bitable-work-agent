from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import pytest

import app.services.retrieval_v2_indexing as retrieval_indexing
from app.models.stage12_retrieval import (
    Stage12RetrievalChunk,
    Stage12RetrievalProfile,
    Stage12RetrievalSource,
)
from app.schemas.retrieval_v2 import EmbeddingProfileV1, RetrievalProjectionV2
from app.services.retrieval_v2_embeddings import EmbeddingProviderError
from app.services.retrieval_v2_indexing import (
    MemoryRetrievalIndexUnitOfWork,
    process_retrieval_projection_event,
    request_retrieval_projection,
    revoke_retrieval_source,
    rollback_retrieval_profile,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
    initialize_field,
    initialize_lookup_field,
    initialize_relation_field,
    replace_field_permission_policy,
    update_record,
)


NOW = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)
PROFILE_NAME = "stage12.openrouter-bge-m3-v1"


class _CharacterCounter:
    def encode(self, text: str) -> tuple[int, ...]:
        return tuple(ord(character) for character in text)

    def decode(self, token_ids: tuple[int, ...]) -> str:
        return "".join(chr(token_id) for token_id in token_ids)


class _Provider:
    def __init__(
        self,
        *,
        profile: EmbeddingProfileV1 | None = None,
        fail: bool = False,
        output_dimension: int = 1024,
    ) -> None:
        self.profile = profile or _embedding_profile()
        self.fail = fail
        self.output_dimension = output_dimension
        self.document_calls = 0
        self.consumed_input_tokens = 0
        self.estimated_cost_usd = 0.0

    def embed_documents(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        self.document_calls += 1
        if self.fail:
            raise EmbeddingProviderError("embedding_provider_unavailable")
        return tuple(
            tuple(1.0 if index == 0 else 0.0 for index in range(self.output_dimension))
            for _ in texts
        )

    def embed_queries(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        return self.embed_documents(texts)


def _embedding_profile(
    *,
    profile_name: str = PROFILE_NAME,
    revision: str = "baai/bge-m3-20251117",
) -> EmbeddingProfileV1:
    return EmbeddingProfileV1(
        version="embedding-profile.v1",
        profile_name=profile_name,
        model_revision=revision,
        dimension=1024,
        normalization="l2",
        distance_metric="cosine",
        max_input_tokens=8192,
        batch_size=64,
        provider_location="remote",
        data_residency="synthetic-test-only",
    )


def _stored_profile(
    *,
    profile_name: str = PROFILE_NAME,
    status: str = "active",
) -> Stage12RetrievalProfile:
    return Stage12RetrievalProfile(
        id=uuid4(),
        profile_name=profile_name,
        model_revision=(
            "baai/bge-m3-20251117"
            if profile_name == PROFILE_NAME
            else "fallback-revision"
        ),
        dimension=1024,
        normalization="l2",
        distance_metric="cosine",
        max_input_tokens=8192,
        batch_size=64,
        provider_location="remote",
        data_residency="synthetic-test-only",
        profile_hash="a" * 64,
        status=status,
        activated_at=NOW if status == "active" else None,
        retired_at=None,
    )


def _projection(
    *,
    version: int,
    text: str | None = None,
    workspace_id=None,
) -> RetrievalProjectionV2:
    canonical = text or f"[table] Work items\n[record] item-{version}"
    return RetrievalProjectionV2(
        version="retrieval-projection.v2",
        source_type="record",
        source_id="record:synthetic-item",
        source_version=version,
        workspace_id=workspace_id or uuid4(),
        base_id=uuid4(),
        table_id=uuid4(),
        record_id=uuid4(),
        field_ids=(uuid4(),),
        visibility_profile_hash="b" * 64,
        scope_hash="c" * 64,
        content_hash=sha256(canonical.encode("utf-8")).hexdigest(),
        canonical_text=canonical,
    )


def _seed_active(
    uow: MemoryRetrievalIndexUnitOfWork,
    projection: RetrievalProjectionV2,
    *,
    profile_name: str = PROFILE_NAME,
) -> Stage12RetrievalSource:
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
        embedding_profile=profile_name,
        visibility_profile_hash=projection.visibility_profile_hash,
        scope_hash=projection.scope_hash,
        content_hash=projection.content_hash,
        status="indexed",
        is_active=True,
        activated_at=NOW,
        revoked_at=None,
    )
    uow.sources.append(source)
    uow.chunks.append(
        Stage12RetrievalChunk(
            id=uuid4(),
            workspace_id=projection.workspace_id,
            source_id=source.id,
            source_version=projection.source_version,
            ordinal=0,
            chunk_kind="canonical",
            source_type=projection.source_type,
            table_id=projection.table_id,
            record_id=projection.record_id,
            field_ids=list(projection.field_ids),
            start_token=0,
            end_token=1,
            chunk_text=projection.canonical_text,
            keyword_terms=["synthetic"],
            content_hash=projection.content_hash,
            visibility_profile_hash=projection.visibility_profile_hash,
            scope_hash=projection.scope_hash,
            embedding_profile=profile_name,
            embedding=[1.0] + [0.0] * 1023,
            status="indexed",
            revoked_at=None,
        )
    )
    return source


def test_projection_request_is_reference_only_and_idempotent() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection(version=1)

    first = request_retrieval_projection(
        uow,
        projection,
        trace_id="stage12-index-request",
        now=NOW,
    )
    replay = request_retrieval_projection(
        uow,
        projection,
        trace_id="stage12-index-request",
        now=NOW,
    )

    assert replay is first
    assert len(uow.outbox_events) == 1
    assert set(first.payload) == {
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
    rendered = str(first.payload)
    assert projection.canonical_text not in rendered
    assert "field_ids" not in rendered


def test_source_change_event_is_generic_reference_only_and_idempotent() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    projection = _projection(version=2)

    first = retrieval_indexing.request_retrieval_source_change(
        uow,
        workspace_id=projection.workspace_id,
        base_id=projection.base_id,
        table_id=projection.table_id,
        record_id=projection.record_id,
        source_type=projection.source_type,
        source_identity=projection.source_id,
        source_version=projection.source_version,
        mutation_kind="record_changed",
        trace_id="stage12-source-changed-v2",
        now=NOW,
    )
    replay = retrieval_indexing.request_retrieval_source_change(
        uow,
        workspace_id=projection.workspace_id,
        base_id=projection.base_id,
        table_id=projection.table_id,
        record_id=projection.record_id,
        source_type=projection.source_type,
        source_identity=projection.source_id,
        source_version=projection.source_version,
        mutation_kind="record_changed",
        trace_id="stage12-source-changed-v2",
        now=NOW,
    )

    assert replay is first
    assert len(uow.outbox_events) == 1
    assert first.event_type == "stage12.retrieval_source.changed"
    assert first.status == "pending"
    assert first.payload == {
        "workspace_id": str(projection.workspace_id),
        "base_id": str(projection.base_id),
        "table_id": str(projection.table_id),
        "record_id": str(projection.record_id),
        "source_type": "record",
        "source_id": projection.source_id,
        "source_version": 2,
        "mutation_kind": "record_changed",
        "trace_id": first.trace_id,
    }
    rendered = str(first.payload)
    assert projection.canonical_text not in rendered
    assert "field_ids" not in rendered
    assert "content_hash" not in rendered
    assert "visibility_profile_hash" not in rendered
    assert "scope_hash" not in rendered


def test_source_change_expands_one_request_per_authorized_visibility_profile() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    first = _projection(version=2)
    second = first.model_copy(
        update={
            "visibility_profile_hash": "d" * 64,
            "scope_hash": "e" * 64,
        }
    )
    source_event = retrieval_indexing.request_retrieval_source_change(
        uow,
        workspace_id=first.workspace_id,
        base_id=first.base_id,
        table_id=first.table_id,
        record_id=first.record_id,
        source_type=first.source_type,
        source_identity=first.source_id,
        source_version=first.source_version,
        mutation_kind="record_changed",
        trace_id="stage12-expand-source-v2",
        now=NOW,
    )

    result = retrieval_indexing.expand_retrieval_source_change_event(
        uow,
        source_event,
        projection_reader=lambda reference: (second, first),
        registered_scope_profiles=frozenset(
            {
                (
                    first.visibility_profile_hash,
                    first.scope_hash,
                ),
                (
                    second.visibility_profile_hash,
                    second.scope_hash,
                ),
            }
        ),
        now=NOW,
    )

    assert result.status == "expanded"
    assert result.requested_projection_count == 2
    assert result.error_code == "none"
    assert source_event.status == "processed"
    projection_events = [
        event
        for event in uow.outbox_events
        if event.event_type == "stage12.retrieval_projection.requested"
    ]
    assert len(projection_events) == 2
    assert {
        event.payload["visibility_profile_hash"] for event in projection_events
    } == {"b" * 64, "d" * 64}


def test_source_change_rejects_entire_fanout_when_projection_identity_drifts() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    current = _projection(version=2)
    drifted = _projection(version=3, workspace_id=current.workspace_id)
    source_event = retrieval_indexing.request_retrieval_source_change(
        uow,
        workspace_id=current.workspace_id,
        base_id=current.base_id,
        table_id=current.table_id,
        record_id=current.record_id,
        source_type=current.source_type,
        source_identity=current.source_id,
        source_version=current.source_version,
        mutation_kind="record_changed",
        trace_id="stage12-expand-drift",
        now=NOW,
    )

    result = retrieval_indexing.expand_retrieval_source_change_event(
        uow,
        source_event,
        projection_reader=lambda reference: (current, drifted),
        registered_scope_profiles=frozenset(
            {(current.visibility_profile_hash, current.scope_hash)}
        ),
        now=NOW,
    )

    assert result.status == "failed"
    assert result.requested_projection_count == 0
    assert result.error_code == "retrieval_source_projection_invalid"
    assert source_event.status == "pending"
    assert len(uow.outbox_events) == 1


def test_source_change_rejects_unregistered_visibility_scope_profile() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    current = _projection(version=2)
    unregistered = current.model_copy(
        update={
            "visibility_profile_hash": "f" * 64,
            "scope_hash": "0" * 64,
        }
    )
    source_event = retrieval_indexing.request_retrieval_source_change(
        uow,
        workspace_id=current.workspace_id,
        base_id=current.base_id,
        table_id=current.table_id,
        record_id=current.record_id,
        source_type=current.source_type,
        source_identity=current.source_id,
        source_version=current.source_version,
        mutation_kind="record_changed",
        trace_id="stage12-unregistered-scope",
        now=NOW,
    )

    result = retrieval_indexing.expand_retrieval_source_change_event(
        uow,
        source_event,
        projection_reader=lambda reference: (unregistered,),
        registered_scope_profiles=frozenset(
            {(current.visibility_profile_hash, current.scope_hash)}
        ),
        now=NOW,
    )

    assert result.status == "failed"
    assert result.error_code == "retrieval_source_scope_unregistered"
    assert result.requested_projection_count == 0
    assert source_event.status == "pending"
    assert len(uow.outbox_events) == 1


def test_source_change_rejects_forged_aggregate_or_multiline_source_id() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    current = _projection(version=2)
    source_event = retrieval_indexing.request_retrieval_source_change(
        uow,
        workspace_id=current.workspace_id,
        base_id=current.base_id,
        table_id=current.table_id,
        record_id=current.record_id,
        source_type=current.source_type,
        source_identity=current.source_id,
        source_version=current.source_version,
        mutation_kind="record_changed",
        trace_id="stage12-forged-source-reference",
        now=NOW,
    )
    source_event.aggregate_id = "record:forged"
    source_event.payload = {
        **source_event.payload,
        "source_id": f"{current.source_id}\nforged",
    }
    reads = 0

    def _reader(reference):
        nonlocal reads
        reads += 1
        return (current,)

    result = retrieval_indexing.expand_retrieval_source_change_event(
        uow,
        source_event,
        projection_reader=_reader,
        registered_scope_profiles=frozenset(
            {(current.visibility_profile_hash, current.scope_hash)}
        ),
        now=NOW,
    )

    assert result.status == "failed"
    assert result.error_code == "retrieval_source_change_event_invalid"
    assert reads == 0
    assert source_event.status == "pending"


def test_stage12_mutation_hook_is_default_off_and_workspace_allowlisted() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Stage12", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="Work")
    disabled_table = create_table(
        uow,
        base.id,
        name="Disabled",
        key="disabled",
    )
    create_field(
        uow,
        disabled_table.id,
        name="Title",
        key="title",
        field_type="text",
    )
    create_record(uow, disabled_table.id, values={"title": "not indexed"})

    assert uow.outbox_events == []
    assert "stage12_schema_version" not in disabled_table.settings

    uow.stage12_retrieval_workspace_ids = frozenset({workspace.id})
    enabled_table = create_table(
        uow,
        base.id,
        name="Enabled",
        key="enabled",
    )
    create_field(
        uow,
        enabled_table.id,
        name="Title",
        key="title",
        field_type="text",
    )
    create_record(uow, enabled_table.id, values={"title": "reference only"})

    changes = [
        event
        for event in uow.outbox_events
        if event.event_type == "stage12.retrieval_source.changed"
    ]
    assert len(changes) == 4
    assert enabled_table.settings["stage12_schema_version"] == 2
    assert all(event.payload["workspace_id"] == str(workspace.id) for event in changes)


def test_stage06_schema_and_record_mutations_emit_generic_change_events() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Stage12", owner_user_id="owner-1")
    uow.stage12_retrieval_workspace_ids = frozenset({workspace.id})
    base = create_base(uow, workspace.id, name="Work", actor=actor)
    table = create_table(
        uow,
        base.id,
        name="Tasks",
        key="tasks",
        actor=actor,
    )
    field = create_field(
        uow,
        table.id,
        name="Private note",
        key="private_note",
        field_type="text",
        actor=actor,
    )
    record = create_record(
        uow,
        table.id,
        values={"private_note": "must-never-enter-outbox"},
        actor=actor,
    )
    update_record(
        uow,
        record.id,
        values={"private_note": "second-secret"},
        expected_version=1,
        actor=actor,
    )

    changes = [
        event
        for event in uow.outbox_events
        if event.event_type == "stage12.retrieval_source.changed"
    ]
    assert [
        (
            event.payload["source_type"],
            event.payload["source_id"],
            event.payload["source_version"],
            event.payload["mutation_kind"],
        )
        for event in changes
    ] == [
        ("schema_table", f"schema_table:{table.id}", 1, "schema_changed"),
        ("schema_table", f"schema_table:{table.id}", 2, "schema_changed"),
        ("schema_field", f"schema_field:{field.id}", 2, "schema_changed"),
        ("record", f"record:{record.id}", 1, "record_changed"),
        ("record", f"record:{record.id}", 2, "record_changed"),
    ]
    rendered = str([event.payload for event in changes])
    assert "must-never-enter-outbox" not in rendered
    assert "second-secret" not in rendered
    assert "field_ids" not in rendered
    assert "visibility_profile_hash" not in rendered


def test_stage06_schema_mutations_advance_durable_table_schema_version() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace = create_workspace(uow, name="Stage12", owner_user_id="owner-1")
    uow.stage12_retrieval_workspace_ids = frozenset({workspace.id})
    base = create_base(uow, workspace.id, name="Work")
    table = create_table(uow, base.id, name="Tasks", key="tasks")

    first = create_field(
        uow,
        table.id,
        name="Title",
        key="title",
        field_type="text",
    )
    second = create_field(
        uow,
        table.id,
        name="Status",
        key="status",
        field_type="status",
    )

    assert table.settings["stage12_schema_version"] == 3
    changes = [
        event.payload
        for event in uow.outbox_events
        if event.event_type == "stage12.retrieval_source.changed"
    ]
    assert [
        (payload["source_id"], payload["source_version"]) for payload in changes
    ] == [
        (f"schema_table:{table.id}", 1),
        (f"schema_table:{table.id}", 2),
        (f"schema_field:{first.id}", 2),
        (f"schema_table:{table.id}", 3),
        (f"schema_field:{second.id}", 3),
    ]


def test_stage06_link_mutations_emit_link_change_only_for_linked_fields() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    actor = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Stage12", owner_user_id="owner-1")
    uow.stage12_retrieval_workspace_ids = frozenset({workspace.id})
    base = create_base(uow, workspace.id, name="Work", actor=actor)
    targets = create_table(uow, base.id, name="Targets", key="targets", actor=actor)
    source = create_table(uow, base.id, name="Tasks", key="tasks", actor=actor)
    create_field(
        uow,
        targets.id,
        name="Name",
        key="name",
        field_type="text",
        actor=actor,
    )
    create_field(
        uow,
        source.id,
        name="Title",
        key="title",
        field_type="text",
        actor=actor,
    )
    link = create_field(
        uow,
        source.id,
        name="Target",
        key="target",
        field_type="linked_record",
        options={"target_table_id": str(targets.id)},
        actor=actor,
    )
    target = create_record(uow, targets.id, values={"name": "Alpha"}, actor=actor)
    record = create_record(
        uow,
        source.id,
        values={"title": "One", "target": [str(target.id)]},
        actor=actor,
    )
    update_record(
        uow,
        record.id,
        values={"title": "Two"},
        expected_version=1,
        actor=actor,
    )
    update_record(
        uow,
        record.id,
        values={link.key: []},
        expected_version=2,
        actor=actor,
    )

    link_events = [
        event
        for event in uow.outbox_events
        if event.event_type == "stage12.retrieval_source.changed"
        and event.payload["source_id"] == f"record:{record.id}"
        and event.payload["mutation_kind"] == "link_changed"
    ]
    assert [event.payload["source_version"] for event in link_events] == [1, 3]
    assert all("field_ids" not in event.payload for event in link_events)


def test_permission_contraction_revokes_affected_vectors_before_rebuild_events() -> (
    None
):
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Stage12", owner_user_id="owner-1")
    uow.stage12_retrieval_workspace_ids = frozenset({workspace.id})
    base = create_base(uow, workspace.id, name="Work", actor=owner)
    table = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    private = create_field(
        uow,
        table.id,
        name="Private",
        key="private",
        field_type="text",
        actor=owner,
    )
    public = create_field(
        uow,
        table.id,
        name="Public",
        key="public",
        field_type="text",
        actor=owner,
    )
    affected_record = create_record(
        uow,
        table.id,
        values={"private": "secret", "public": "visible"},
        actor=owner,
    )
    unaffected_record = create_record(
        uow,
        table.id,
        values={"public": "other"},
        actor=owner,
    )
    affected_text = "[table] Tasks\n[record] affected\n[Private] secret"
    affected_projection = RetrievalProjectionV2(
        version="retrieval-projection.v2",
        source_type="record",
        source_id=f"record:{affected_record.id}",
        source_version=affected_record.version,
        workspace_id=workspace.id,
        base_id=base.id,
        table_id=table.id,
        record_id=affected_record.id,
        field_ids=(private.id,),
        visibility_profile_hash="7" * 64,
        scope_hash="8" * 64,
        content_hash=sha256(affected_text.encode("utf-8")).hexdigest(),
        canonical_text=affected_text,
    )
    unaffected_text = "[table] Tasks\n[record] unaffected\n[Public] other"
    unaffected_projection = RetrievalProjectionV2(
        version="retrieval-projection.v2",
        source_type="record",
        source_id=f"record:{unaffected_record.id}",
        source_version=unaffected_record.version,
        workspace_id=workspace.id,
        base_id=base.id,
        table_id=table.id,
        record_id=unaffected_record.id,
        field_ids=(public.id,),
        visibility_profile_hash="9" * 64,
        scope_hash="a" * 64,
        content_hash=sha256(unaffected_text.encode("utf-8")).hexdigest(),
        canonical_text=unaffected_text,
    )
    affected_source = _seed_active(
        uow.stage12_retrieval_uow,
        affected_projection,
    )
    unaffected_source = _seed_active(
        uow.stage12_retrieval_uow,
        unaffected_projection,
    )

    replace_field_permission_policy(
        uow,
        table.id,
        private.id,
        policy={
            "owner": "write",
            "admin": "write",
            "builder": "write",
            "operator": "read",
            "viewer": "hidden",
        },
        expected_permission_version=1,
        actor=owner,
    )

    assert affected_source.status == "revoked"
    assert affected_source.is_active is False
    assert all(
        chunk.status == "revoked"
        for chunk in uow.stage12_retrieval_uow.list_chunks(affected_source.id)
    )
    assert unaffected_source.status == "indexed"
    assert unaffected_source.is_active is True
    permission_changes = [
        event.payload
        for event in uow.outbox_events
        if event.event_type == "stage12.retrieval_source.changed"
        and event.payload["mutation_kind"] == "permission_changed"
    ]
    assert {payload["source_id"] for payload in permission_changes} == {
        f"schema_table:{table.id}",
        f"schema_field:{private.id}",
        f"record:{affected_record.id}",
        f"record:{unaffected_record.id}",
    }
    assert any(
        event.event_type == "stage12.retrieval_projection.revoked"
        for event in uow.outbox_events
    )
    assert "secret" not in str(permission_changes)


def test_stage07_field_initializers_emit_versioned_schema_change_events() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Stage12", owner_user_id="owner-1")
    uow.stage12_retrieval_workspace_ids = frozenset({workspace.id})
    base = create_base(uow, workspace.id, name="Work", actor=owner)
    targets = create_table(uow, base.id, name="Targets", key="targets", actor=owner)
    tasks = create_table(uow, base.id, name="Tasks", key="tasks", actor=owner)
    target_label = initialize_field(
        uow,
        targets.id,
        name="Name",
        field_type="text",
        required=False,
        choices=None,
        actor=owner,
    ).field
    relation = initialize_relation_field(
        uow,
        tasks.id,
        name="Target",
        target_table_id=targets.id,
        required=False,
        actor=owner,
    ).field
    lookup = initialize_lookup_field(
        uow,
        tasks.id,
        name="Target name",
        source_relation_field_id=relation.id,
        target_field_id=target_label.id,
        aggregation="values",
        actor=owner,
    ).field

    assert targets.settings["stage12_schema_version"] == 2
    assert tasks.settings["stage12_schema_version"] == 3
    schema_events = [
        event.payload
        for event in uow.outbox_events
        if event.event_type == "stage12.retrieval_source.changed"
        and event.payload["mutation_kind"] == "schema_changed"
    ]
    assert (f"schema_field:{target_label.id}", 2) in {
        (payload["source_id"], payload["source_version"]) for payload in schema_events
    }
    assert (f"schema_field:{relation.id}", 2) in {
        (payload["source_id"], payload["source_version"]) for payload in schema_events
    }
    assert (f"schema_field:{lookup.id}", 3) in {
        (payload["source_id"], payload["source_version"]) for payload in schema_events
    }


def test_process_rereads_current_projection_and_atomically_switches_version() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    uow.profiles.append(_stored_profile())
    first = _projection(version=1)
    second = _projection(version=2, workspace_id=first.workspace_id)
    old = _seed_active(uow, first)
    event = request_retrieval_projection(
        uow,
        second,
        trace_id="stage12-index-v2",
        now=NOW,
    )
    reads = 0

    def reader(reference: dict[str, object]) -> RetrievalProjectionV2:
        nonlocal reads
        reads += 1
        return second

    result = process_retrieval_projection_event(
        uow,
        event,
        projection_reader=reader,
        token_counter=_CharacterCounter(),
        provider=_Provider(),
        now=NOW,
    )

    assert result.status == "indexed"
    assert reads == 1
    assert old.is_active is False
    assert old.status == "stale"
    assert [source.source_version for source in uow.sources if source.is_active] == [2]
    assert all(
        chunk.status == "stale" for chunk in uow.chunks if chunk.source_id == old.id
    )
    assert event.status == "processed"

    replay = process_retrieval_projection_event(
        uow,
        event,
        projection_reader=reader,
        token_counter=_CharacterCounter(),
        provider=_Provider(),
        now=NOW,
    )
    assert replay.status == "indexed"
    assert reads == 1
    assert len(uow.sources) == 2


def test_projection_request_rejects_forged_source_before_authorized_read() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    uow.profiles.append(_stored_profile())
    projection = _projection(version=1)
    event = request_retrieval_projection(
        uow,
        projection,
        trace_id="stage12-forged-projection-request",
        now=NOW,
    )
    event.aggregate_id = "record:forged"
    event.payload = {
        **event.payload,
        "source_id": f"{projection.source_id}\nforged",
    }
    reads = 0

    def _reader(reference):
        nonlocal reads
        reads += 1
        return projection

    result = process_retrieval_projection_event(
        uow,
        event,
        projection_reader=_reader,
        token_counter=_CharacterCounter(),
        provider=_Provider(),
        now=NOW,
    )

    assert result.status == "failed"
    assert result.error_code == "retrieval_projection_event_invalid"
    assert reads == 0
    assert event.status == "pending"


def test_stale_event_is_discarded_without_provider_call() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    uow.profiles.append(_stored_profile())
    requested = _projection(version=2)
    current = _projection(version=3, workspace_id=requested.workspace_id)
    event = request_retrieval_projection(
        uow,
        requested,
        trace_id="stage12-stale-v2",
        now=NOW,
    )
    provider = _Provider()

    result = process_retrieval_projection_event(
        uow,
        event,
        projection_reader=lambda reference: current,
        token_counter=_CharacterCounter(),
        provider=provider,
        now=NOW,
    )

    assert result.status == "discarded"
    assert result.error_code == "retrieval_projection_stale"
    assert provider.document_calls == 0
    assert not uow.sources
    assert event.status == "processed"


@pytest.mark.parametrize(
    ("provider", "error_code"),
    (
        (_Provider(fail=True), "embedding_provider_unavailable"),
        (_Provider(output_dimension=8), "embedding_output_invalid"),
        (
            _Provider(profile=_embedding_profile(revision="drifted-revision")),
            "embedding_profile_mismatch",
        ),
    ),
)
def test_provider_or_profile_failure_retains_previous_active_version(
    provider: _Provider,
    error_code: str,
) -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    uow.profiles.append(_stored_profile())
    first = _projection(version=1)
    second = _projection(version=2, workspace_id=first.workspace_id)
    old = _seed_active(uow, first)
    event = request_retrieval_projection(
        uow,
        second,
        trace_id=f"stage12-failure-{error_code}",
        now=NOW,
    )

    result = process_retrieval_projection_event(
        uow,
        event,
        projection_reader=lambda reference: second,
        token_counter=_CharacterCounter(),
        provider=provider,
        now=NOW,
    )

    assert result.status == "failed"
    assert result.error_code == error_code
    assert old.is_active is True
    assert old.status == "indexed"
    assert len(uow.sources) == 1
    assert event.status == "pending"


def test_same_content_reuses_vector_but_activates_current_source_version() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    uow.profiles.append(_stored_profile())
    first = _projection(version=1, text="same authorized text")
    second = _projection(
        version=2,
        text="same authorized text",
        workspace_id=first.workspace_id,
    )
    old = _seed_active(uow, first)
    event = request_retrieval_projection(
        uow,
        second,
        trace_id="stage12-content-noop",
        now=NOW,
    )
    provider = _Provider()

    result = process_retrieval_projection_event(
        uow,
        event,
        projection_reader=lambda reference: second,
        token_counter=_CharacterCounter(),
        provider=provider,
        now=NOW,
    )

    assert result.status == "indexed"
    assert result.reused_embedding is True
    assert provider.document_calls == 0
    assert old.is_active is False
    assert [source.source_version for source in uow.sources if source.is_active] == [2]


def test_revoke_hides_source_and_chunks_before_cleanup_event() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    first = _projection(version=1)
    old = _seed_active(uow, first)

    result = revoke_retrieval_source(
        uow,
        workspace_id=first.workspace_id,
        source_type=first.source_type,
        source_identity=first.source_id,
        visibility_profile_hash=first.visibility_profile_hash,
        reason_code="permission_contracted",
        now=NOW,
    )

    assert result.revoked_source_count == 1
    assert result.revoked_chunk_count == 1
    assert old.status == "revoked"
    assert old.is_active is False
    assert all(chunk.status == "revoked" for chunk in uow.chunks)
    assert result.event.event_type == "stage12.retrieval_projection.revoked"
    assert "chunk_text" not in str(result.event.payload)

    replay = revoke_retrieval_source(
        uow,
        workspace_id=first.workspace_id,
        source_type=first.source_type,
        source_identity=first.source_id,
        visibility_profile_hash=first.visibility_profile_hash,
        reason_code="permission_contracted",
        now=NOW,
    )

    assert replay.event is result.event
    assert replay.revoked_source_count == 0
    assert replay.revoked_chunk_count == 0


def test_profile_rollback_reactivates_latest_fallback_version() -> None:
    uow = MemoryRetrievalIndexUnitOfWork()
    selected = _stored_profile()
    fallback = _stored_profile(
        profile_name="stage12.local-fallback-v1", status="retired"
    )
    fallback.retired_at = NOW
    uow.profiles.extend([selected, fallback])
    projection = _projection(version=1)
    selected_source = _seed_active(uow, projection)
    fallback_source = _seed_active(
        uow,
        _projection(
            version=2,
            text="fallback text",
            workspace_id=projection.workspace_id,
        ),
        profile_name=fallback.profile_name,
    )
    fallback_source.is_active = False
    fallback_source.status = "stale"

    result = rollback_retrieval_profile(
        uow,
        selected_profile=selected.profile_name,
        fallback_profile=fallback.profile_name,
        now=NOW,
    )

    assert result.status == "rolled_back"
    assert selected.status == "retired"
    assert fallback.status == "active"
    assert selected_source.is_active is False
    assert fallback_source.is_active is True


def test_profile_rollback_is_atomic_when_activation_write_fails() -> None:
    class _FailingUnitOfWork(MemoryRetrievalIndexUnitOfWork):
        def __init__(self) -> None:
            super().__init__()
            self.flush_count = 0

        def flush(self) -> None:
            self.flush_count += 1
            if self.flush_count == 4:
                raise RuntimeError("synthetic_write_failure")

    uow = _FailingUnitOfWork()
    selected = _stored_profile()
    fallback = _stored_profile(
        profile_name="stage12.local-fallback-v1",
        status="retired",
    )
    fallback.retired_at = NOW
    uow.profiles.extend([selected, fallback])
    projection = _projection(version=1)
    selected_source = _seed_active(uow, projection)
    fallback_source = _seed_active(
        uow,
        _projection(
            version=2,
            text="fallback text",
            workspace_id=projection.workspace_id,
        ),
        profile_name=fallback.profile_name,
    )
    fallback_source.is_active = False
    fallback_source.status = "stale"

    with pytest.raises(RuntimeError, match="synthetic_write_failure"):
        rollback_retrieval_profile(
            uow,
            selected_profile=selected.profile_name,
            fallback_profile=fallback.profile_name,
            now=NOW,
        )

    assert selected.status == "active"
    assert selected.retired_at is None
    assert fallback.status == "retired"
    assert fallback.retired_at == NOW
    assert selected_source.is_active is True
    assert selected_source.status == "indexed"
    assert fallback_source.is_active is False
    assert fallback_source.status == "stale"
