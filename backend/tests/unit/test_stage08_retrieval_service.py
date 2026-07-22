from datetime import UTC, datetime, timedelta
import hashlib
import json
from uuid import UUID, uuid4

import pytest

from app.models.outbox import OutboxEvent
from app.models.stage08_knowledge import Stage08KnowledgeChunk, Stage08KnowledgeSource
from app.runtime.stage08_memory_contracts import (
    MemoryMaterializationProjection,
    MemoryScopeProjection,
    MemorySourceRef,
)
from app.services.permissions import Actor
from app.services.stage06_platform import (
    InMemoryStage06PlatformUnitOfWork,
    create_base,
    create_field,
    create_record,
    create_table,
    create_workspace,
)
from app.models.stage06_platform import WorkspaceMember
from app.services.stage06_platform import PlatformValidationError
from app.services.stage08_memory import materialize_memory_from_projection
from app.services.stage08_retrieval import (
    process_knowledge_cleanup_event,
    process_knowledge_index_event,
    register_memory_knowledge_source,
    request_knowledge_reindex,
    revoke_knowledge_source,
)
from app.services.stage08_retrieval_embeddings import (
    TEST_EMBEDDING_DIMENSION,
    TEST_EMBEDDING_PROFILE,
    TEST_EMBEDDING_VERSION,
    TestHashEmbeddingProvider,
)


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
INDEX_EVENT = "stage08.knowledge.index_requested"
CLEANUP_EVENT = "stage08.knowledge.cleanup_requested"
REFERENCE_PAYLOAD_KEYS = {
    "workspace_id",
    "knowledge_source_id",
    "content_version",
    "projection_hash",
    "trace_id",
}


def _trace_ref(caller_trace_id: str) -> str:
    return hashlib.sha256(
        f"stage08-knowledge-trace-v1:{caller_trace_id}".encode("utf-8")
    ).hexdigest()


def _fixture():
    uow = InMemoryStage06PlatformUnitOfWork()
    owner = Actor(actor_type="user", actor_id="owner-1", role="owner")
    workspace = create_workspace(uow, name="Retrieval", owner_user_id="owner-1")
    base = create_base(uow, workspace.id, name="CRM")
    table = create_table(uow, base.id, name="Customers", key="customers")
    create_field(uow, table.id, name="Customer", key="customer", field_type="text")
    create_field(uow, table.id, name="Decision", key="decision", field_type="text")
    record = create_record(
        uow,
        table.id,
        values={"customer": "Acme", "decision": "approved"},
        actor=owner,
    )
    return uow, owner, workspace, base, table, record


def _projection(
    workspace_id: UUID,
    base_id: UUID,
    table_id: UUID,
    record_id: UUID,
    record_version: int,
    *,
    memory_type: str = "decision",
    decision: str = "approved",
    identity_token: str | None = None,
    valid_until: datetime | None = None,
) -> MemoryMaterializationProjection:
    return MemoryMaterializationProjection(
        memory_type=memory_type,
        scope=MemoryScopeProjection(
            workspace_id=workspace_id,
            base_id=base_id,
            table_id=table_id,
            identity_token=identity_token,
        ),
        payload={"customer": "Acme", "decision": decision},
        source_refs=(
            MemorySourceRef(
                source_kind="platform_record",
                source_id=record_id,
                source_version=record_version,
                field_keys=("customer", "decision"),
            ),
        ),
        valid_until=valid_until,
    )


def _materialize_current_memory():
    uow, owner, workspace, base, table, record = _fixture()
    item = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW,
    )
    return uow, owner, workspace, base, table, record, item


def _register(uow, owner, item, *, now: datetime = NOW, trace_id: str = "trace-d2"):
    return register_memory_knowledge_source(
        uow,
        item.id,
        actor=owner,
        now=now,
        trace_id=trace_id,
    )


def test_controlled_reindex_reuses_reference_event_and_replays_one_safe_receipt() -> None:
    uow, owner, workspace, _base, _table, _record, item = _materialize_current_memory()
    registration = _register(uow, owner, item)
    assert registration is not None
    audit_count = len(uow.audit_events)

    first = request_knowledge_reindex(
        uow,
        workspace.id,
        registration.source.id,
        actor=owner,
        idempotency_key="reindex-safe-1",
        trace_id="reindex-trace-1",
        now=NOW,
    )
    replay = request_knowledge_reindex(
        uow,
        workspace.id,
        registration.source.id,
        actor=owner,
        idempotency_key="reindex-safe-1",
        trace_id="reindex-trace-1",
        now=NOW,
    )

    assert first == replay
    assert first.ticket_id == registration.event.id
    assert first.status == "accepted"
    assert repr(first) == "KnowledgeReindexReceipt(status='accepted')"
    assert len(uow.outbox_events) == 1
    assert len(uow.idempotency_records) == 1
    assert len(uow.audit_events) == audit_count + 1
    audit = uow.audit_events[-1]
    assert audit.event_type == "stage08.knowledge.reindex_requested"
    assert audit.trace_id == uow.idempotency_records[0].trace_id
    serialized = json.dumps(
        {
            "outbox": registration.event.payload,
            "audit": {
                "before": audit.before_state,
                "after": audit.after_state,
                "permission": audit.permission_snapshot,
            },
            "idempotency": uow.idempotency_records[0].response_ref,
        },
        sort_keys=True,
    ).casefold()
    for forbidden in (
        "projection_text",
        "chunk_text",
        "embedding",
        "keyword_terms",
        "query",
        "memory payload",
        "group_chat_ref",
        "telegram",
    ):
        assert forbidden not in serialized


def test_controlled_reindex_conflicts_on_changed_source_or_trace() -> None:
    uow, owner, workspace, _base, _table, _record, item = _materialize_current_memory()
    registration = _register(uow, owner, item)
    assert registration is not None
    request_knowledge_reindex(
        uow,
        workspace.id,
        registration.source.id,
        actor=owner,
        idempotency_key="reindex-conflict",
        trace_id="trace-one",
        now=NOW,
    )

    with pytest.raises(PlatformValidationError) as trace_error:
        request_knowledge_reindex(
            uow,
            workspace.id,
            registration.source.id,
            actor=owner,
            idempotency_key="reindex-conflict",
            trace_id="trace-two",
            now=NOW,
        )
    assert trace_error.value.code == "idempotency_conflict"

    other_source = _source(workspace.id, 2, uuid4())
    other_source.source_ref = dict(registration.source.source_ref)
    other_source.scope = dict(registration.source.scope)
    other_source.logical_source_fingerprint = registration.source.logical_source_fingerprint
    other_source.projection_hash = registration.source.projection_hash
    other_source.projection_text = registration.source.projection_text
    other_source.content_version = registration.source.content_version
    uow.knowledge_sources.append(other_source)
    with pytest.raises(PlatformValidationError) as source_error:
        request_knowledge_reindex(
            uow,
            workspace.id,
            other_source.id,
            actor=owner,
            idempotency_key="reindex-conflict",
            trace_id="trace-one",
            now=NOW,
        )
    assert source_error.value.code == "idempotency_conflict"


@pytest.mark.parametrize("role", ["builder", "operator", "viewer", "manager"])
def test_controlled_reindex_fails_closed_for_noncanonical_manager_roles(role: str) -> None:
    uow, owner, workspace, _base, _table, _record, item = _materialize_current_memory()
    registration = _register(uow, owner, item)
    assert registration is not None
    user_id = f"{role}-1"
    uow.add_workspace_member(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=user_id,
            role=role,
            status="active",
            version=1,
        )
    )

    with pytest.raises(PlatformValidationError) as error:
        request_knowledge_reindex(
            uow,
            workspace.id,
            registration.source.id,
            actor=Actor(actor_type="user", actor_id=user_id, role=role),
            idempotency_key=f"reindex-role-{role}",
            trace_id=f"trace-role-{role}",
            now=NOW,
        )

    assert error.value.code == "knowledge_reindex_forbidden"
    assert uow.idempotency_records == []


@pytest.mark.parametrize("source_state", ["replaced", "revoked", "deleted", "expired"])
def test_controlled_reindex_rejects_terminal_or_memory_drifted_source(
    source_state: str,
) -> None:
    uow, owner, workspace, _base, _table, _record, item = _materialize_current_memory()
    registration = _register(uow, owner, item)
    assert registration is not None
    registration.source.status = source_state
    registration.source.projection_text = None

    with pytest.raises(PlatformValidationError) as error:
        request_knowledge_reindex(
            uow,
            workspace.id,
            registration.source.id,
            actor=owner,
            idempotency_key=f"reindex-state-{source_state}",
            trace_id=f"trace-state-{source_state}",
            now=NOW,
        )

    assert error.value.code == "knowledge_reindex_source_invalid"
    assert uow.idempotency_records == []


def test_controlled_reindex_revalidates_read_only_memory_lineage_and_type() -> None:
    uow, owner, workspace, _base, _table, _record, item = _materialize_current_memory()
    registration = _register(uow, owner, item)
    assert registration is not None
    item.status = "revoked"

    with pytest.raises(PlatformValidationError) as memory_error:
        request_knowledge_reindex(
            uow,
            workspace.id,
            registration.source.id,
            actor=owner,
            idempotency_key="reindex-memory-drift",
            trace_id="trace-memory-drift",
            now=NOW,
        )
    assert memory_error.value.code == "knowledge_reindex_source_invalid"

    item.status = "active"
    registration.source.source_type = "document_projection"
    with pytest.raises(PlatformValidationError) as type_error:
        request_knowledge_reindex(
            uow,
            workspace.id,
            registration.source.id,
            actor=owner,
            idempotency_key="reindex-source-type",
            trace_id="trace-source-type",
            now=NOW,
        )
    assert type_error.value.code == "knowledge_reindex_source_invalid"


def test_current_non_group_memory_registers_safe_source_and_reference_event() -> None:
    uow, owner, workspace, base, table, _record, item = _materialize_current_memory()

    result = _register(uow, owner, item)

    assert result is not None
    assert result.source.workspace_id == workspace.id
    assert result.source.source_type == "memory_item"
    assert result.source.status == "active"
    assert result.source.content_version == item.version
    assert result.source.scope == {
        "workspace_id": str(workspace.id),
        "base_id": str(base.id),
        "table_id": str(table.id),
    }
    expected_text = json.dumps(
        {
            "memory_type": "decision",
            "payload": {"customer": "Acme", "decision": "approved"},
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    assert result.source.projection_text == expected_text
    assert result.source.projection_hash == hashlib.sha256(
        expected_text.encode("utf-8")
    ).hexdigest()
    assert result.source.logical_source_fingerprint == hashlib.sha256(
        f"memory_lineage:{item.id}".encode("utf-8")
    ).hexdigest()
    assert result.source.source_ref["memory_item_id"] == str(item.id)
    assert result.event.event_type == INDEX_EVENT
    assert result.event.aggregate_type == "stage08_knowledge_source"
    assert result.event.aggregate_id == str(result.source.id)
    assert result.event.status == "pending"
    assert set(result.event.payload) == REFERENCE_PAYLOAD_KEYS
    assert result.event.payload == result.outbox_payload


def test_registration_calls_memory_projection_in_read_only_mode(monkeypatch) -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()
    from app.services import stage08_retrieval as retrieval_service

    original = retrieval_service.read_memory_projection
    calls: list[str] = []

    def tracking_read(*args, **kwargs):
        calls.append(kwargs["lifecycle_mode"])
        return original(*args, **kwargs)

    monkeypatch.setattr(retrieval_service, "read_memory_projection", tracking_read)

    assert _register(uow, owner, item) is not None
    assert calls == ["read_only"]


def test_missing_revoked_expired_and_source_drift_memory_are_rejected() -> None:
    uow, owner, workspace, base, table, record = _fixture()
    assert (
        register_memory_knowledge_source(
            uow, uuid4(), actor=owner, now=NOW, trace_id="missing"
        )
        is None
    )

    expired = materialize_memory_from_projection(
        uow,
        _projection(
            workspace.id,
            base.id,
            table.id,
            record.id,
            record.version,
            valid_until=NOW - timedelta(seconds=1),
        ),
        actor=owner,
        now=NOW - timedelta(seconds=2),
    )
    assert _register(uow, owner, expired) is None
    assert expired.status == "active"

    expired.valid_until = None
    expired.status = "revoked"
    assert _register(uow, owner, expired) is None

    expired.status = "active"
    record.version += 1
    assert _register(uow, owner, expired) is None
    assert uow.knowledge_sources == []
    assert uow.outbox_events == []


@pytest.mark.parametrize("rejected_kind", ["group_scope", "telegram_source"])
def test_group_scoped_and_telegram_memory_never_enter_rag(rejected_kind: str) -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()
    if rejected_kind == "group_scope":
        item.scope["group_chat_ref"] = f"stage06-binding:{uuid4()}"
    else:
        item.source_refs[0]["source_kind"] = "telegram_message"

    assert _register(uow, owner, item) is None
    assert uow.knowledge_sources == []
    assert uow.outbox_events == []


def test_adapter_explicitly_rejects_readable_group_projection_and_client_like_extra_keys(
    monkeypatch,
) -> None:
    uow, owner, workspace, _base, _table, _record, item = _materialize_current_memory()
    from app.services import stage08_retrieval as retrieval_service

    safe_projection = {
        "id": item.id,
        "memory_type": "decision",
        "version": item.version,
        "scope": {
            "workspace_id": str(workspace.id),
            "group_chat_ref": f"stage06-binding:{uuid4()}",
        },
        "payload": {"decision": "approved"},
        "valid_until": None,
    }
    monkeypatch.setattr(
        retrieval_service,
        "read_memory_projection",
        lambda *args, **kwargs: safe_projection,
    )
    assert _register(uow, owner, item) is None

    client_like = dict(safe_projection)
    client_like["scope"] = {"workspace_id": str(workspace.id)}
    client_like["projection_text"] = "client supplied"
    item.scope.pop("group_chat_ref", None)
    monkeypatch.setattr(
        retrieval_service,
        "read_memory_projection",
        lambda *args, **kwargs: client_like,
    )
    assert _register(uow, owner, item) is None
    assert uow.knowledge_sources == []


def test_adapter_rejects_projection_workspace_scope_mismatch(monkeypatch) -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()
    from app.services import stage08_retrieval as retrieval_service

    mismatched_projection = {
        "id": item.id,
        "memory_type": "decision",
        "version": item.version,
        "scope": {"workspace_id": str(uuid4())},
        "payload": {"decision": "approved"},
        "valid_until": None,
    }
    monkeypatch.setattr(
        retrieval_service,
        "read_memory_projection",
        lambda *args, **kwargs: mismatched_projection,
    )

    assert _register(uow, owner, item) is None
    assert uow.knowledge_sources == []
    assert uow.outbox_events == []


def test_adapter_rejects_projection_version_mismatch_with_current_item(
    monkeypatch,
) -> None:
    uow, owner, workspace, _base, _table, _record, item = _materialize_current_memory()
    from app.services import stage08_retrieval as retrieval_service

    mismatched_projection = {
        "id": item.id,
        "memory_type": "decision",
        "version": item.version + 1,
        "scope": {"workspace_id": str(workspace.id)},
        "payload": {"decision": "approved"},
        "valid_until": None,
    }
    monkeypatch.setattr(
        retrieval_service,
        "read_memory_projection",
        lambda *args, **kwargs: mismatched_projection,
    )

    assert _register(uow, owner, item) is None
    assert uow.knowledge_sources == []
    assert uow.outbox_events == []


def test_canonical_projection_excludes_item_scope_source_and_raw_carriers() -> None:
    uow, owner, workspace, base, table, record, item = _materialize_current_memory()
    result = _register(uow, owner, item)

    assert result is not None
    text = result.source.projection_text or ""
    for forbidden in (
        str(item.id),
        str(workspace.id),
        str(base.id),
        str(table.id),
        str(record.id),
        "source_ref",
        "identity_token",
        "group_chat_ref",
        "raw_text",
        "telegram",
    ):
        assert forbidden not in text
    assert "approved" not in repr(result)
    assert str(item.id) not in repr(result)


def test_payload_with_scope_or_raw_carrier_keys_is_rejected_fail_closed() -> None:
    forbidden_keys = ("workspace_id", "identity_token", "raw_caption", "source_refs")
    for forbidden_key in forbidden_keys:
        uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()
        item.payload[forbidden_key] = "must-not-index"

        assert _register(uow, owner, item) is None
        assert uow.knowledge_sources == []
        assert uow.outbox_events == []


def test_index_outbox_payload_has_exact_reference_keys_and_redacts_bodies() -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()
    result = _register(uow, owner, item, trace_id="trace-reference")

    assert result is not None
    assert set(result.event.payload) == REFERENCE_PAYLOAD_KEYS
    assert result.event.payload["trace_id"] == _trace_ref("trace-reference")
    assert result.event.trace_id == _trace_ref("trace-reference")
    serialized = json.dumps(result.event.payload, sort_keys=True)
    for forbidden in (
        "projection_text",
        "body",
        "payload",
        "source_ref",
        "scope",
        "actor",
        "approved",
        "Acme",
    ):
        assert forbidden not in serialized


def test_same_memory_version_and_hash_replay_reuses_source_and_event() -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()

    first = _register(uow, owner, item)
    second = _register(
        uow,
        owner,
        item,
        now=NOW + timedelta(seconds=1),
        trace_id="different-replay-trace",
    )

    assert first is not None and second is not None
    assert second.source is first.source
    assert second.event is first.event
    assert len(uow.knowledge_sources) == 1
    assert len(uow.outbox_events) == 1


def test_real_memory_supersession_replaces_old_source_and_requests_cleanup_once() -> None:
    uow, owner, workspace, base, table, record, first_item = _materialize_current_memory()
    first = _register(uow, owner, first_item)
    assert first is not None
    old_chunk = Stage08KnowledgeChunk(
        id=uuid4(),
        workspace_id=first.source.workspace_id,
        source_id=first.source.id,
        source_version=first.source.content_version,
        ordinal=0,
        chunk_text="old safe projection chunk",
        chunk_hash=hashlib.sha256(b"old safe projection chunk").hexdigest(),
        keyword_terms=["old"],
        embedding_profile="stage08.test-hash-v1",
        embedding_version=1,
        embedding=[0.0] * 8,
        status="indexed",
        created_at=NOW,
        updated_at=NOW,
    )
    uow.add_knowledge_chunk(old_chunk)

    record.version += 1
    second_item = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW + timedelta(seconds=1),
    )
    assert second_item.id != first_item.id
    assert second_item.supersedes_id == first_item.id
    second = _register(
        uow,
        owner,
        second_item,
        now=NOW + timedelta(seconds=2),
        trace_id="trace-v2",
    )
    replay = _register(
        uow,
        owner,
        second_item,
        now=NOW + timedelta(seconds=3),
        trace_id="trace-v2-replay",
    )

    assert second is not None and replay is not None
    assert first.source.status == "replaced"
    assert old_chunk.status == "stale"
    assert second.source.status == "active"
    assert second.source.supersedes_id == first.source.id
    assert second.source.content_version == 2
    assert second.source.source_ref["memory_item_id"] == str(second_item.id)
    assert (
        second.source.logical_source_fingerprint
        == first.source.logical_source_fingerprint
        == hashlib.sha256(
            f"memory_lineage:{first_item.id}".encode("utf-8")
        ).hexdigest()
    )
    assert replay.source is second.source
    assert replay.event is second.event
    assert len(uow.knowledge_sources) == 2
    assert sum(event.event_type == INDEX_EVENT for event in uow.outbox_events) == 2
    cleanup_events = [
        event for event in uow.outbox_events if event.event_type == CLEANUP_EVENT
    ]
    assert len(cleanup_events) == 1
    assert cleanup_events[0].aggregate_id == str(first.source.id)
    expected_cleanup_trace = _trace_ref(
        "source-replaced:"
        f"{first.source.id}:"
        f"{first.source.content_version}:"
        f"{first.source.projection_hash}"
    )
    assert cleanup_events[0].payload["trace_id"] == expected_cleanup_trace
    assert cleanup_events[0].trace_id == expected_cleanup_trace
    assert len(uow.outbox_events) == 3


def test_cross_memory_type_lineage_collision_fails_closed_without_mutation() -> None:
    (
        uow,
        owner,
        workspace,
        base,
        table,
        record,
        first_item,
        old_source,
        old_chunk,
    ) = _collision_fixture()
    unrelated = materialize_memory_from_projection(
        uow,
        _projection(
            workspace.id,
            base.id,
            table.id,
            record.id,
            record.version,
            memory_type="preference",
        ),
        actor=owner,
        now=NOW + timedelta(seconds=2),
    )
    unrelated.supersedes_id = first_item.id
    unrelated.version = first_item.version + 1
    original_events = tuple(uow.outbox_events)
    original_projection_text = old_source.projection_text

    result = _register(
        uow,
        owner,
        unrelated,
        now=NOW + timedelta(seconds=3),
        trace_id="cross-type-collision",
    )

    assert result is None
    assert old_source.status == "active"
    assert old_source.projection_text == original_projection_text
    assert old_source.supersedes_id is None
    assert old_chunk.status == "indexed"
    assert len(uow.knowledge_sources) == 1
    assert tuple(uow.outbox_events) == original_events


@pytest.mark.parametrize("scope_collision", ["table_id", "identity_token"])
def test_same_type_different_scope_lineage_collision_fails_closed_without_mutation(
    scope_collision: str,
) -> None:
    (
        uow,
        owner,
        workspace,
        base,
        table,
        record,
        first_item,
        old_source,
        old_chunk,
    ) = _collision_fixture()
    if scope_collision == "table_id":
        unrelated_table = create_table(
            uow,
            base.id,
            name="Unrelated",
            key="unrelated",
        )
        create_field(
            uow,
            unrelated_table.id,
            name="Customer",
            key="customer",
            field_type="text",
        )
        create_field(
            uow,
            unrelated_table.id,
            name="Decision",
            key="decision",
            field_type="text",
        )
        unrelated_record = create_record(
            uow,
            unrelated_table.id,
            values={"customer": "Acme", "decision": "approved"},
            actor=owner,
        )
        unrelated_projection = _projection(
            workspace.id,
            base.id,
            unrelated_table.id,
            unrelated_record.id,
            unrelated_record.version,
        )
    else:
        unrelated_projection = _projection(
            workspace.id,
            base.id,
            table.id,
            record.id,
            record.version,
            identity_token="b" * 64,
        )
    unrelated = materialize_memory_from_projection(
        uow,
        unrelated_projection,
        actor=owner,
        now=NOW + timedelta(seconds=2),
    )
    unrelated.supersedes_id = first_item.id
    unrelated.version = first_item.version + 1
    original_events = tuple(uow.outbox_events)
    original_projection_text = old_source.projection_text

    result = _register(
        uow,
        owner,
        unrelated,
        now=NOW + timedelta(seconds=3),
        trace_id=f"scope-collision-{scope_collision}",
    )

    assert result is None
    assert old_source.status == "active"
    assert old_source.projection_text == original_projection_text
    assert old_source.supersedes_id is None
    assert old_chunk.status == "indexed"
    assert len(uow.knowledge_sources) == 1
    assert tuple(uow.outbox_events) == original_events


@pytest.mark.parametrize(
    "broken_lineage",
    [
        "missing",
        "cycle",
        "cross_workspace",
        "non_monotonic",
        "invalid_status",
        "invalid_metadata",
    ],
)
def test_broken_memory_lineage_fails_closed_without_source_or_event(
    broken_lineage: str,
) -> None:
    uow, owner, workspace, base, table, record, first_item = _materialize_current_memory()
    record.version += 1
    current_item = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW + timedelta(seconds=1),
    )
    if broken_lineage == "missing":
        current_item.supersedes_id = uuid4()
    elif broken_lineage == "cycle":
        first_item.supersedes_id = current_item.id
    elif broken_lineage == "cross_workspace":
        foreign = create_workspace(uow, name="Foreign", owner_user_id="owner-1")
        first_item.workspace_id = foreign.id
    elif broken_lineage == "non_monotonic":
        first_item.version = current_item.version
    elif broken_lineage == "invalid_status":
        first_item.status = "active"
    else:
        first_item.source_refs[0]["source_kind"] = "unapproved_source"

    assert _register(uow, owner, current_item) is None
    assert uow.knowledge_sources == []
    assert uow.outbox_events == []


def test_caller_trace_is_persisted_only_as_documented_sha256_reference() -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()
    sentinel = "projection-body-secret-Acme-approved"

    result = _register(uow, owner, item, trace_id=sentinel)

    assert result is not None
    expected = _trace_ref(sentinel)
    assert result.event.payload["trace_id"] == expected
    assert result.event.trace_id == expected
    assert sentinel not in json.dumps(result.event.payload, sort_keys=True)
    assert sentinel not in repr(result)
    assert sentinel not in repr(result.event)
    assert sentinel not in repr(result.outbox_payload)


def test_replay_rejects_existing_event_with_raw_trace_carrier() -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()
    first = _register(uow, owner, item, trace_id="safe-first-trace")
    assert first is not None
    first.event.payload["trace_id"] = "raw-body-secret"
    first.event.trace_id = "raw-body-secret"

    replay = _register(uow, owner, item, trace_id="safe-replay-trace")

    assert replay is None
    assert len(uow.knowledge_sources) == 1
    assert len(uow.outbox_events) == 1


@pytest.mark.parametrize("invalid_trace", ["   ", "trace\ncarrier", "x" * 121])
def test_invalid_caller_trace_fails_closed_without_echo_or_persistence(
    invalid_trace: str,
) -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()

    assert _register(uow, owner, item, trace_id=invalid_trace) is None
    assert uow.knowledge_sources == []
    assert uow.outbox_events == []


@pytest.mark.parametrize("source_status", ["active", "pending"])
def test_revoke_scrubs_source_marks_chunks_stale_and_emits_one_cleanup_event(
    source_status: str,
) -> None:
    uow, owner, _workspace, _base, _table, _record, item = _materialize_current_memory()
    registration = _register(uow, owner, item)
    assert registration is not None
    registration.source.status = source_status
    chunk = Stage08KnowledgeChunk(
        id=uuid4(),
        workspace_id=registration.source.workspace_id,
        source_id=registration.source.id,
        source_version=registration.source.content_version,
        ordinal=0,
        chunk_text="safe projection chunk",
        chunk_hash=hashlib.sha256(b"safe projection chunk").hexdigest(),
        keyword_terms=["safe"],
        embedding_profile="stage08.test-hash-v1",
        embedding_version=1,
        embedding=[0.0] * 8,
        status="indexed",
        created_at=NOW,
        updated_at=NOW,
    )
    uow.add_knowledge_chunk(chunk)

    first = revoke_knowledge_source(
        uow,
        registration.source.id,
        now=NOW + timedelta(seconds=1),
        reason_code="memory_revoked",
    )
    second = revoke_knowledge_source(
        uow,
        registration.source.id,
        now=NOW + timedelta(seconds=2),
        reason_code="memory_revoked",
    )

    assert first is not None
    assert second is None
    assert registration.source.status == "revoked"
    assert registration.source.projection_text is None
    assert registration.source.revoked_at == NOW + timedelta(seconds=1)
    assert chunk.status == "stale"
    assert chunk.chunk_text == "safe projection chunk"
    cleanup_events = [event for event in uow.outbox_events if event.event_type == CLEANUP_EVENT]
    assert len(cleanup_events) == 1
    assert set(cleanup_events[0].payload) == REFERENCE_PAYLOAD_KEYS
    assert "memory_revoked" not in json.dumps(cleanup_events[0].payload)


def test_inmemory_knowledge_uow_methods_filter_and_order_exactly() -> None:
    uow = InMemoryStage06PlatformUnitOfWork()
    workspace_id = uuid4()
    foreign_workspace_id = uuid4()
    fingerprint = "a" * 64
    sources = [
        _source(workspace_id, 2, UUID("00000000-0000-0000-0000-000000000002")),
        _source(workspace_id, 1, UUID("00000000-0000-0000-0000-000000000001")),
        _source(
            foreign_workspace_id,
            1,
            UUID("00000000-0000-0000-0000-000000000003"),
        ),
    ]
    for source in sources:
        source.logical_source_fingerprint = fingerprint
        uow.add_knowledge_source(source)

    chunks = [
        _chunk(sources[0], 1, UUID("00000000-0000-0000-0000-000000000012")),
        _chunk(sources[0], 0, UUID("00000000-0000-0000-0000-000000000011")),
        _chunk(sources[1], 0, UUID("00000000-0000-0000-0000-000000000010")),
    ]
    for chunk in chunks:
        uow.add_knowledge_chunk(chunk)

    assert uow.get_knowledge_source(sources[0].id) is sources[0]
    assert uow.lock_knowledge_source_for_lifecycle(sources[0].id) is sources[0]
    assert uow.get_knowledge_source(uuid4()) is None
    assert uow.list_knowledge_sources(workspace_id) == [sources[1], sources[0]]
    assert uow.list_knowledge_chunks(sources[0].id, 2) == [chunks[1], chunks[0]]
    assert uow.list_knowledge_chunks(sources[0].id, 1) == []


def test_index_event_creates_deterministic_vectors_and_replay_is_idempotent() -> None:
    uow, registration = _index_fixture()

    first = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW + timedelta(seconds=1),
    )
    first_vectors = [tuple(chunk.embedding or ()) for chunk in uow.knowledge_chunks]
    second = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW + timedelta(seconds=2),
    )

    assert first.status == second.status == "indexed"
    assert first.error_code == second.error_code == "none"
    assert first.indexed_chunk_count == second.indexed_chunk_count == 1
    assert len(uow.knowledge_chunks) == 1
    assert first_vectors == [tuple(uow.knowledge_chunks[0].embedding or ())]
    chunk = uow.knowledge_chunks[0]
    assert chunk.status == "indexed"
    assert chunk.embedding_profile == TEST_EMBEDDING_PROFILE
    assert chunk.embedding_version == TEST_EMBEDDING_VERSION
    assert len(chunk.embedding or ()) == TEST_EMBEDDING_DIMENSION
    assert all(isinstance(value, float) for value in chunk.embedding or ())
    assert registration.event.status == "processed"
    assert registration.event.processed_at == NOW + timedelta(seconds=1)
    assert "approved" not in repr(first)


@pytest.mark.parametrize("conflict", ["metadata", "finite_vector"])
def test_index_replay_conflict_stales_and_scrubs_existing_indexed_chunks(
    conflict: str,
) -> None:
    uow, registration = _index_fixture()
    indexed = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW + timedelta(seconds=1),
    )
    assert indexed.status == "indexed"
    chunk = uow.knowledge_chunks[0]
    if conflict == "metadata":
        chunk.keyword_terms = ["tampered"]
    else:
        drifted = list(chunk.embedding or ())
        drifted[0] = 0.0 if drifted[0] != 0.0 else 0.25
        chunk.embedding = drifted
    original_projection = registration.source.projection_text
    registration.event.status = "pending"
    registration.event.processed_at = None

    result = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW + timedelta(seconds=2),
    )

    assert result.status == "failed"
    assert result.error_code == "knowledge_index_failed"
    assert result.indexed_chunk_count == 0
    assert registration.source.status == "active"
    assert registration.source.projection_text == original_projection
    assert registration.event.status == "pending"
    assert registration.event.processed_at is None
    assert chunk.status == "stale"
    assert chunk.chunk_text is None
    assert chunk.keyword_terms == []
    assert chunk.embedding is None
    assert chunk.embedding_profile is None
    assert chunk.embedding_version is None
    assert not [candidate for candidate in uow.knowledge_chunks if candidate.status == "indexed"]


@pytest.mark.parametrize(
    ("drift", "expected_status"),
    [
        ("source_hash", "discarded"),
        ("source_version", "discarded"),
        ("source_workspace", "discarded"),
        ("replaced", "discarded"),
        ("revoked", "discarded"),
        ("expired", "discarded"),
        ("deleted", "discarded"),
        ("event_type", "failed"),
        ("aggregate", "failed"),
        ("payload", "failed"),
        ("raw_trace", "failed"),
    ],
)
def test_index_event_drift_and_terminal_sources_never_create_readable_chunks(
    drift: str,
    expected_status: str,
) -> None:
    uow, registration = _index_fixture()
    sentinel = "raw-provider-body-secret-approved"
    if drift == "source_hash":
        registration.source.projection_hash = "a" * 64
    elif drift == "source_version":
        registration.source.content_version += 1
    elif drift == "source_workspace":
        registration.source.workspace_id = uuid4()
    elif drift in {"replaced", "revoked", "deleted"}:
        registration.source.status = drift
    elif drift == "expired":
        registration.source.valid_until = NOW - timedelta(seconds=1)
    elif drift == "event_type":
        registration.event.event_type = "stage08.knowledge.unapproved"
    elif drift == "aggregate":
        registration.event.aggregate_id = str(uuid4())
    elif drift == "payload":
        registration.event.payload["projection_text"] = sentinel
    else:
        registration.event.trace_id = sentinel
        registration.event.payload["trace_id"] = sentinel

    result = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW,
    )

    assert result.status == expected_status
    assert result.error_code == "knowledge_index_source_invalid"
    assert result.indexed_chunk_count == 0
    assert uow.knowledge_chunks == []
    assert sentinel not in repr(result)


def test_source_lock_failure_returns_fixed_code_without_event_or_body_echo(
    monkeypatch,
) -> None:
    uow, registration = _index_fixture()
    sentinel = "raw-lock-error-source-body-approved"

    def fail_lock(_source_id):
        raise RuntimeError(sentinel)

    monkeypatch.setattr(uow, "lock_knowledge_source_for_lifecycle", fail_lock)

    index_result = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW,
    )
    cleanup_event = _reference_event(
        registration.source,
        event_type=CLEANUP_EVENT,
        trace_id=_trace_ref("lock-cleanup"),
    )
    cleanup_result = process_knowledge_cleanup_event(
        uow,
        cleanup_event,
        now=NOW,
    )

    assert index_result.status == cleanup_result.status == "failed"
    assert index_result.error_code == cleanup_result.error_code == "knowledge_index_failed"
    assert sentinel not in repr(index_result)
    assert sentinel not in repr(cleanup_result)
    assert registration.event.status == "pending"
    assert cleanup_event.status == "pending"
    assert uow.knowledge_chunks == []


@pytest.mark.parametrize("flow", ["index", "cleanup"])
def test_post_lock_chunk_read_failure_returns_fixed_code_without_mutation(
    flow: str,
    monkeypatch,
) -> None:
    uow, registration = _index_fixture()
    sentinel = "raw-chunk-read-error-approved"
    if flow == "index":
        event = registration.event
        invoke = lambda: process_knowledge_index_event(
            uow,
            event,
            provider=TestHashEmbeddingProvider(),
            now=NOW,
        )
    else:
        registration.source.status = "replaced"
        existing = _chunk(registration.source, 0, uuid4())
        existing.status = "stale"
        uow.add_knowledge_chunk(existing)
        event = _reference_event(
            registration.source,
            event_type=CLEANUP_EVENT,
            trace_id=_trace_ref("chunk-read-cleanup"),
        )
        invoke = lambda: process_knowledge_cleanup_event(uow, event, now=NOW)
    snapshot = _worker_state_snapshot(uow, registration.source, event)

    def fail_list(_source_id, _source_version):
        raise RuntimeError(sentinel)

    monkeypatch.setattr(uow, "list_knowledge_chunks", fail_list)
    result = invoke()

    assert result.status == "failed"
    assert result.error_code == "knowledge_index_failed"
    assert getattr(result, "indexed_chunk_count", 0) == 0
    assert getattr(result, "cleaned_chunk_count", 0) == 0
    assert _worker_state_snapshot(uow, registration.source, event) == snapshot
    assert sentinel not in repr(result)
    assert sentinel not in json.dumps(event.payload, sort_keys=True)
    assert sentinel not in event.trace_id


@pytest.mark.parametrize("invalid_source", ["computed_hash", "cap", "conflict"])
def test_hash_cap_and_existing_chunk_conflicts_leave_no_readable_partial_index(
    invalid_source: str,
) -> None:
    uow, registration = _index_fixture()
    if invalid_source == "computed_hash":
        registration.source.projection_text += " changed"
    elif invalid_source == "cap":
        oversized = "A" * 1_000_001
        oversized_hash = hashlib.sha256(oversized.encode("utf-8")).hexdigest()
        registration.source.projection_text = oversized
        registration.source.projection_hash = oversized_hash
        registration.event.payload["projection_hash"] = oversized_hash
    else:
        conflict = _chunk(registration.source, 0, uuid4())
        conflict.chunk_hash = "f" * 64
        uow.add_knowledge_chunk(conflict)

    result = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW,
    )

    assert result.status in {"discarded", "failed"}
    assert result.error_code in {
        "knowledge_index_source_invalid",
        "knowledge_index_failed",
    }
    assert not [chunk for chunk in uow.knowledge_chunks if chunk.status == "indexed"]


class _InvalidEmbeddingProvider:
    profile = TEST_EMBEDDING_PROFILE
    version = TEST_EMBEDDING_VERSION
    dimension = TEST_EMBEDDING_DIMENSION

    def __init__(self, mode: str) -> None:
        self.mode = mode

    def embed_batch(self, profile, texts):
        if self.mode == "raises":
            raise RuntimeError("raw-provider-body-secret")
        if self.mode == "partial":
            return ((0.0,) * TEST_EMBEDDING_DIMENSION,)
        if self.mode == "dimension":
            return tuple((0.0,) * 7 for _ in texts)
        if self.mode == "nonfinite":
            return tuple((float("nan"),) * TEST_EMBEDDING_DIMENSION for _ in texts)
        if self.mode == "overflow":
            return tuple(
                (10**10000,) + (0.0,) * (TEST_EMBEDDING_DIMENSION - 1)
                for _ in texts
            )
        if self.mode == "exceptional_iterable":
            return tuple(
                _ExceptionalEmbedding((0.0,) * TEST_EMBEDDING_DIMENSION)
                for _ in texts
            )
        raise AssertionError("unsupported test mode")


class _ExceptionalEmbedding(tuple):
    def __iter__(self):
        raise RuntimeError("raw-provider-iterable-secret")


class _InvalidEmbeddingProfileProvider(TestHashEmbeddingProvider):
    def __init__(self, *, profile=TEST_EMBEDDING_PROFILE, version=1, dimension=8):
        self.profile = profile
        self.version = version
        self.dimension = dimension


@pytest.mark.parametrize(
    ("provider", "error_code"),
    [
        (None, "embedding_provider_unavailable"),
        (_InvalidEmbeddingProvider("raises"), "knowledge_index_failed"),
        (_InvalidEmbeddingProvider("partial"), "embedding_output_invalid"),
        (_InvalidEmbeddingProvider("dimension"), "embedding_output_invalid"),
        (_InvalidEmbeddingProvider("nonfinite"), "embedding_output_invalid"),
        (_InvalidEmbeddingProvider("overflow"), "embedding_output_invalid"),
        (_InvalidEmbeddingProvider("exceptional_iterable"), "embedding_output_invalid"),
    ],
)
def test_embedding_failure_never_creates_partial_readable_chunks(
    provider,
    error_code: str,
) -> None:
    uow, registration = _index_fixture(payload_text="A" * 1_500)

    result = process_knowledge_index_event(
        uow,
        registration.event,
        provider=provider,
        now=NOW + timedelta(seconds=1),
    )

    assert result.status == "failed"
    assert result.error_code == error_code
    assert result.indexed_chunk_count == 0
    assert not [chunk for chunk in uow.knowledge_chunks if chunk.status == "indexed"]
    assert registration.event.status == "pending"
    assert registration.event.processed_at is None
    assert "raw-provider-body-secret" not in repr(result)
    assert "raw-provider-iterable-secret" not in repr(result)


@pytest.mark.parametrize(
    "provider",
    [
        _InvalidEmbeddingProfileProvider(profile="stage08.unapproved"),
        _InvalidEmbeddingProfileProvider(version=True),
        _InvalidEmbeddingProfileProvider(version=2),
        _InvalidEmbeddingProfileProvider(dimension=7),
    ],
)
def test_embedding_profile_metadata_is_strictly_fixed(provider) -> None:
    uow, registration = _index_fixture()

    result = process_knowledge_index_event(
        uow,
        registration.event,
        provider=provider,
        now=NOW,
    )

    assert result.status == "failed"
    assert result.error_code == "embedding_output_invalid"
    assert uow.knowledge_chunks == []
    assert registration.event.status == "pending"


@pytest.mark.parametrize("terminal_status", ["replaced", "revoked", "expired", "deleted"])
def test_cleanup_scrubs_source_and_chunks_and_replay_cannot_restore_data(
    terminal_status: str,
) -> None:
    uow, registration = _index_fixture()
    indexed = process_knowledge_index_event(
        uow,
        registration.event,
        provider=TestHashEmbeddingProvider(),
        now=NOW + timedelta(seconds=1),
    )
    assert indexed.status == "indexed"
    registration.source.status = terminal_status
    for chunk in uow.knowledge_chunks:
        chunk.status = "stale"
    cleanup_event = _reference_event(
        registration.source,
        event_type=CLEANUP_EVENT,
        trace_id=_trace_ref(f"cleanup-{terminal_status}"),
    )
    uow.add_outbox_event(cleanup_event)

    first = process_knowledge_cleanup_event(
        uow,
        cleanup_event,
        now=NOW + timedelta(seconds=2),
    )
    second = process_knowledge_cleanup_event(
        uow,
        cleanup_event,
        now=NOW + timedelta(seconds=3),
    )

    assert first.status == second.status == "cleaned"
    assert first.cleaned_chunk_count == second.cleaned_chunk_count == 1
    assert registration.source.projection_text is None
    chunk = uow.knowledge_chunks[0]
    assert chunk.status == "deleted"
    assert chunk.chunk_text is None
    assert chunk.keyword_terms == []
    assert chunk.embedding is None
    assert chunk.embedding_profile is None
    assert chunk.embedding_version is None
    assert chunk.deleted_at == NOW + timedelta(seconds=2)
    assert cleanup_event.status == "processed"
    assert cleanup_event.processed_at == NOW + timedelta(seconds=2)


def test_cleanup_event_cannot_delete_active_or_hash_drifted_source() -> None:
    for drift in ("active", "hash"):
        uow, registration = _index_fixture()
        indexed = process_knowledge_index_event(
            uow,
            registration.event,
            provider=TestHashEmbeddingProvider(),
            now=NOW + timedelta(seconds=1),
        )
        assert indexed.status == "indexed"
        cleanup_event = _reference_event(
            registration.source,
            event_type=CLEANUP_EVENT,
            trace_id=_trace_ref(f"cleanup-{drift}"),
        )
        if drift == "hash":
            cleanup_event.payload["projection_hash"] = "f" * 64
            registration.source.status = "replaced"
        original_text = registration.source.projection_text
        original_chunk = uow.knowledge_chunks[0]

        result = process_knowledge_cleanup_event(uow, cleanup_event, now=NOW)

        assert result.status == "discarded"
        assert result.error_code == "knowledge_index_source_invalid"
        assert registration.source.projection_text == original_text
        assert original_chunk.status == "indexed"
        assert original_chunk.chunk_text is not None


def test_test_hash_provider_is_explicit_only_and_fixed_profile() -> None:
    provider = TestHashEmbeddingProvider()
    assert provider.profile == TEST_EMBEDDING_PROFILE
    assert provider.version == TEST_EMBEDDING_VERSION
    assert provider.dimension == TEST_EMBEDDING_DIMENSION
    assert provider.embed_batch(TEST_EMBEDDING_PROFILE, ("same",)) == (
        provider.embed_batch(TEST_EMBEDDING_PROFILE, ("same",))[0],
    )

    uow, registration = _index_fixture()
    implicit = process_knowledge_index_event(
        uow,
        registration.event,
        now=NOW,
    )
    assert implicit.status == "failed"
    assert implicit.error_code == "embedding_provider_unavailable"
    assert uow.knowledge_chunks == []


def _index_fixture(*, payload_text: str = "approved"):
    uow, owner, workspace, base, table, record = _fixture()
    record.values["decision"] = payload_text
    item = materialize_memory_from_projection(
        uow,
        _projection(
            workspace.id,
            base.id,
            table.id,
            record.id,
            record.version,
            decision=payload_text,
        ),
        actor=owner,
        now=NOW,
    )
    registration = _register(uow, owner, item, trace_id="trace-d3-index")
    assert registration is not None
    return uow, registration


def _reference_event(
    source: Stage08KnowledgeSource,
    *,
    event_type: str,
    trace_id: str,
) -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        event_type=event_type,
        aggregate_type="stage08_knowledge_source",
        aggregate_id=str(source.id),
        payload={
            "workspace_id": str(source.workspace_id),
            "knowledge_source_id": str(source.id),
            "content_version": source.content_version,
            "projection_hash": source.projection_hash,
            "trace_id": trace_id,
        },
        status="pending",
        attempts=0,
        attempt_count=0,
        max_attempts=3,
        idempotency_key=f"stage08:test:{event_type}:{source.id}",
        trace_id=trace_id,
        created_at=NOW,
    )


def _worker_state_snapshot(
    uow: InMemoryStage06PlatformUnitOfWork,
    source: Stage08KnowledgeSource,
    event: OutboxEvent,
) -> tuple:
    return (
        (
            source.status,
            source.projection_text,
            source.projection_hash,
            source.updated_at,
        ),
        tuple(
            (
                chunk.id,
                chunk.workspace_id,
                chunk.source_id,
                chunk.source_version,
                chunk.ordinal,
                chunk.status,
                chunk.chunk_text,
                tuple(chunk.keyword_terms),
                tuple(chunk.embedding or ()),
                chunk.embedding_profile,
                chunk.embedding_version,
                chunk.deleted_at,
                chunk.updated_at,
            )
            for chunk in uow.knowledge_chunks
        ),
        (
            event.status,
            event.processed_at,
            dict(event.payload),
            event.trace_id,
            event.last_error,
            event.last_error_redacted,
        ),
    )


def _source(workspace_id: UUID, version: int, source_id: UUID) -> Stage08KnowledgeSource:
    return Stage08KnowledgeSource(
        id=source_id,
        workspace_id=workspace_id,
        source_type="memory_item",
        status="active",
        source_ref={"kind": "memory_item"},
        scope={"workspace_id": str(workspace_id)},
        logical_source_fingerprint="a" * 64,
        projection_hash="b" * 64,
        projection_text="safe",
        content_version=version,
        created_at=NOW,
        updated_at=NOW,
    )


def _collision_fixture():
    uow, owner, workspace, base, table, record, first_item = (
        _materialize_current_memory()
    )
    registration = _register(uow, owner, first_item)
    assert registration is not None
    old_chunk = _chunk(registration.source, 0, uuid4())
    old_chunk.status = "indexed"
    uow.add_knowledge_chunk(old_chunk)
    record.version += 1
    second_item = materialize_memory_from_projection(
        uow,
        _projection(workspace.id, base.id, table.id, record.id, record.version),
        actor=owner,
        now=NOW + timedelta(seconds=1),
    )
    assert first_item.status == "superseded"
    assert second_item.status == "active"
    assert second_item.supersedes_id == first_item.id
    return (
        uow,
        owner,
        workspace,
        base,
        table,
        record,
        first_item,
        registration.source,
        old_chunk,
    )


def _chunk(
    source: Stage08KnowledgeSource,
    ordinal: int,
    chunk_id: UUID,
) -> Stage08KnowledgeChunk:
    return Stage08KnowledgeChunk(
        id=chunk_id,
        workspace_id=source.workspace_id,
        source_id=source.id,
        source_version=source.content_version,
        ordinal=ordinal,
        chunk_text="safe",
        chunk_hash=hashlib.sha256(b"safe").hexdigest(),
        keyword_terms=["safe"],
        status="pending",
        created_at=NOW,
        updated_at=NOW,
    )
